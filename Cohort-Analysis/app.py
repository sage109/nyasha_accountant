#!/usr/bin/env python3
"""
INVENTORY INTEGRITY AGENT (IIA)
===============================
An accounting AI agent that reconciles the perpetual stock ledger to the
general ledger, detects inventory anomalies, computes the NRV / obsolescence
provision (IAS 2 / ASC 330), and drafts adjusting journals for human approval.
The agent never posts; every journal is a DRAFT.

Run:     python inventory_agent.py
Output:  console report + iia_report.md + iia_report.json
Deps:    Python 3.9+ standard library only.
"""

import json
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta, datetime


# ----------------------------------------------------------------------------
# Configuration (in production: read from a controls/policy file)
# ----------------------------------------------------------------------------
@dataclass
class Config:
    n_skus: int = 40
    window_days: int = 90
    seed: int = 42
    recon_tolerance_abs: float = 25.0      # $ tolerance per SKU
    recon_tolerance_pct: float = 0.005     # or 0.5% of ledger value
    writeoff_sigma: float = 2.5            # statistical outlier threshold
    writeoff_hard_cap: float = 1500.0      # policy cap per write-off
    issue_sigma: float = 3.0               # unusual issue-quantity threshold
    provision_policy: dict = field(default_factory=lambda: {
        #  class       (min days no sale, max days no sale, provision rate)
        "slow":     (45, 90, 0.10),
        "dead":     (90, 180, 0.50),
        "obsolete": (180, 10 ** 9, 1.00),
    })
    accounts: dict = field(default_factory=lambda: {
        "inventory":  "1410 Inventory",
        "ap":         "2100 Accounts Payable",
        "cogs":       "5010 COGS",
        "shrink":     "5900 Inventory Shrinkage / Adjustments",
        "allowance":  "1415 Allowance for Inventory Obsolescence",
        "writedown":  "5910 Inventory Write-down Expense",
    })


# ----------------------------------------------------------------------------
# Domain objects
# ----------------------------------------------------------------------------
@dataclass
class SKU:
    code: str
    name: str
    category: str
    velocity: str          # fast | medium | slow | dead
    opening_qty: float
    opening_cost: float    # moving-average unit cost at window start


@dataclass
class Txn:
    id: str
    date: date
    sku: str
    ttype: str             # receipt | issue | adjustment
    qty: float             # signed: + in, - out
    unit_cost: float       # used for receipts; issues/adjustments valued by replay
    posted_gl: bool = True
    note: str = ""


@dataclass
class GLLeg:
    txn_id: str
    date: date
    sku: str
    account: str
    debit: float = 0.0
    credit: float = 0.0


@dataclass
class JournalEntry:
    je_id: str
    date: date
    lines: list            # [(account, debit, credit)]
    memo: str
    source: str
    reason: str
    confidence: float
    status: str = "DRAFT - awaiting approval"


# ----------------------------------------------------------------------------
# Demo ERP: synthetic stock ledger with seeded errors
# ----------------------------------------------------------------------------
def build_demo_world(cfg: Config) -> dict:
    """Generates ~90 days of stock transactions with 5 seeded control failures."""
    rng = random.Random(cfg.seed)
    end = date.today()
    start = end - timedelta(days=cfg.window_days)

    categories = ["Electronics", "Home & Kitchen", "Apparel", "Tools"]
    velocities = ["fast"] * 22 + ["medium"] * 10 + ["slow"] * 5 + ["dead"] * 3
    skus = {}
    for i in range(cfg.n_skus):
        v = velocities[i % len(velocities)]
        code = f"SKU-{1000 + i}"
        skus[code] = SKU(code, f"Product {i + 1} ({v})", rng.choice(categories), v,
                         float(rng.randint(40, 400)), round(rng.uniform(4, 90), 2))

    issue_rate = {"fast": 6.0, "medium": 2.0, "slow": 0.5, "dead": 0.05}  # per week
    issue_max = {"fast": 25, "medium": 12, "slow": 5, "dead": 3}

    txns, seq, dup_done = [], 0, False
    neg_day, neg_sku = start + timedelta(days=45), "SKU-1005"
    big_day = end - timedelta(days=3)
    qty = {c: s.opening_qty for c, s in skus.items()}

    def add(d, sku, ttype, q, unit_cost=None, note=""):
        nonlocal seq
        seq += 1
        t = Txn(f"T{seq:05d}", d, sku, ttype, q,
                unit_cost if unit_cost is not None else 0.0, True, note)
        txns.append(t)
        return t

    day = start
    while day <= end:
        for code, sku in skus.items():
            # Goods received (replenishment)
            if qty[code] < 60 and rng.random() < 0.5:
                r = rng.randint(80, 300)
                add(day, code, "receipt", r,
                    round(sku.opening_cost * rng.uniform(0.95, 1.06), 2),
                    "GRN from supplier")
                qty[code] += r
            # Seeded error 4: mis-keyed issue quantity -> negative stock
            if day == neg_day and code == neg_sku:
                q = max(0, qty[code]) + 40
                add(day, code, "issue", -q, None, "POS batch import")
                qty[code] -= q
                continue
            # Sales issues
            if rng.random() < issue_rate[sku.velocity] / 7.0 and qty[code] > 0:
                q = min(rng.randint(1, issue_max[sku.velocity]), qty[code])
                add(day, code, "issue", -q, None, "Sales issue")
                qty[code] -= q
            # Routine damage write-offs (first one gets duplicated - error 5)
            if rng.random() < 0.02 and qty[code] > 6:
                q = rng.randint(1, 6)
                add(day, code, "adjustment", -q, None, "Damage write-off")
                qty[code] -= q
                if not dup_done:
                    dup_done = True
                    add(day, code, "adjustment", -q, None, "Count correction")
                    qty[code] -= q
        # Seeded error 6: one huge write-off near period end
        if day == big_day:
            cands = [c for c in ("SKU-1002", "SKU-1001", "SKU-1000", "SKU-1006")
                     if qty[c] >= 100] or [c for c in skus if qty[c] >= 60]
            if cands:
                c = cands[0]
                q = min(qty[c], max(1, int(7500 / max(skus[c].opening_cost, 1.0))))
                add(day, c, "adjustment", -q, None, "Water damage - aisle 4")
                qty[c] -= q
        day += timedelta(days=1)

    # Seeded error 1: two receipts exist in the stock ledger but were never posted to GL
    receipts = [t for t in txns if t.ttype == "receipt"]
    mid = [t for t in receipts if start + timedelta(days=20) <= t.date <= end - timedelta(days=20)]
    for t in rng.sample(mid if len(mid) >= 2 else receipts, 2):
        t.posted_gl = False

    # Seeded error 2: one adjustment posted to the GL at double its value
    adjustments = [t for t in txns if t.ttype == "adjustment" and t.note == "Damage write-off"]
    gl_overrides = {adjustments[-1].id: 2.0}

    return {"skus": skus, "txns": txns, "gl_overrides": gl_overrides,
            "period_start": start, "period_end": end}


# ----------------------------------------------------------------------------
# Core engine: moving-average perpetual ledger replay (single source of truth)
# ----------------------------------------------------------------------------
def replay_stock_ledger(skus, txns) -> dict:
    qty = {c: s.opening_qty for c, s in skus.items()}
    value = {c: s.opening_qty * s.opening_cost for c, s in skus.items()}
    min_qty = dict(qty)
    min_qty_date = {c: None for c in skus}
    last_issue, issue_sizes, per_txn_value = {}, defaultdict(list), {}

    for t in sorted(txns, key=lambda x: (x.date, x.id)):
        if t.ttype == "receipt":
            v = t.qty * t.unit_cost
            per_txn_value[t.id] = v
            qty[t.sku] += t.qty
            value[t.sku] += v
        else:  # issue / adjustment: valued at current moving average
            avg = value[t.sku] / qty[t.sku] if qty[t.sku] != 0 else 0.0
            q = v = abs(t.qty) * avg
            per_txn_value[t.id] = v
            if t.qty < 0:
                qty[t.sku] -= q
                value[t.sku] -= v
            else:
                qty[t.sku] += q
                value[t.sku] += v
            if t.ttype == "issue":
                last_issue[t.sku] = t.date
                issue_sizes[t.sku].append(q)
        if qty[t.sku] < min_qty[t.sku]:
            min_qty[t.sku] = qty[t.sku]
            min_qty_date[t.sku] = t.date

    return {"qty_end": qty, "value_end": value, "min_qty": min_qty,
            "min_qty_date": min_qty_date, "last_issue": last_issue,
            "issue_sizes": issue_sizes, "per_txn_value": per_txn_value}


def build_gl_export(world, cfg: Config, valuation: dict) -> list:
    """ERP-side: produces the GL export (with beginning balances and its own errors)."""
    A, gl, overrides = cfg.accounts, [], world["gl_overrides"]
    for code, s in world["skus"].items():  # beginning balances
        ob = round(s.opening_qty * s.opening_cost, 2)
        gl.append(GLLeg(f"OPEN-{code}", world["period_start"], code, A["inventory"], debit=ob))
    for t in world["txns"]:
        if not t.posted_gl:
            continue
        v = round(valuation[t.id] * overrides.get(t.id, 1.0), 2)
        if t.ttype == "receipt":
            gl += [GLLeg(t.id, t.date, t.sku, A["inventory"], debit=v),
                   GLLeg(t.id, t.date, t.sku, A["ap"], credit=v)]
        elif t.ttype == "issue":
            gl += [GLLeg(t.id, t.date, t.sku, A["cogs"], debit=v),
                   GLLeg(t.id, t.date, t.sku, A["inventory"], credit=v)]
        elif t.qty < 0:
            gl += [GLLeg(t.id, t.date, t.sku, A["shrink"], debit=v),
                   GLLeg(t.id, t.date, t.sku, A["inventory"], credit=v)]
        else:
            gl += [GLLeg(t.id, t.date, t.sku, A["inventory"], debit=v),
                   GLLeg(t.id, t.date, t.sku, A["shrink"], credit=v)]
    # Seeded error 3: manual GL journal with no stock movement behind it
    e = world["period_end"]
    gl += [GLLeg("GL-MANUAL-9001", e, "SKU-1003", A["inventory"], debit=1200.00),
           GLLeg("GL-MANUAL-9001", e, "SKU-1003", A["ap"], credit=1200.00)]
    return gl


# ----------------------------------------------------------------------------
# THE AGENT
# ----------------------------------------------------------------------------
class InventoryIntegrityAgent:
    """Perceive -> analyse -> draft -> report, with a full audit trail and
    human-in-the-loop control: the agent drafts, the controller approves."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.memory, self.findings = {}, []
        self.journal_drafts, self.audit_log = [], []
        self._finding_no = 0

    # ---------- infrastructure ----------
    def _log(self, step, action, detail):
        self.audit_log.append({"ts": datetime.now().isoformat(timespec="seconds"),
                               "step": step, "action": action, "detail": detail})

    def _finding(self, module, severity, description, evidence, action):
        self._finding_no += 1
        f = {"id": f"F-{self._finding_no:02d}", "module": module, "severity": severity,
             "description": description, "evidence": evidence, "recommended_action": action}
        self.findings.append(f)
        return f

    @staticmethod
    def _money(x):
        return f"${x:,.2f}"

    # ---------- tool 1: ingest ----------
    def tool_ingest(self, data):
        self.memory.update(data)
        self._log("INGEST", "load sources",
                  f"{len(data['skus'])} SKUs, {len(data['txns'])} stock txns, "
                  f"{len(data['gl'])} GL lines, {data['period_start']}..{data['period_end']}")

    # ---------- tool 2: replay ----------
    def tool_replay(self):
        self.memory["ledger"] = replay_stock_ledger(self.memory["skus"], self.memory["txns"])
        total = sum(self.memory["ledger"]["value_end"].values())
        self._log("REPLAY", "perpetual ledger", f"closing stock value {self._money(total)}")

    # ---------- tool 3: reconcile ----------
    def tool_reconcile(self):
        cfg, led = self.cfg, self.memory["ledger"]
        gl_inv, gl_amt, gl_ids = defaultdict(float), defaultdict(float), set()
        for leg in self.memory["gl"]:
            gl_ids.add(leg.txn_id)
            if leg.account == cfg.accounts["inventory"]:
                gl_amt[leg.txn_id] += leg.debit - leg.credit
                if leg.sku:
                    gl_inv[leg.sku] += leg.debit - leg.credit

        rows, flagged = [], []
        for code in self.memory["skus"]:
            lv, gv = led["value_end"][code], gl_inv.get(code, 0.0)
            var = lv - gv
            tol = max(cfg.recon_tolerance_abs, cfg.recon_tolerance_pct * abs(lv))
            row = {"sku": code, "qty": led["qty_end"][code], "ledger_value": lv,
                   "gl_value": gv, "variance": var, "within_tolerance": abs(var) <= tol}
            rows.append(row)
            if not row["within_tolerance"]:
                flagged.append(row)

        txn_ids = {t.id for t in self.memory["txns"]}
        opening_ids = {l.txn_id for l in self.memory["gl"] if l.txn_id.startswith("OPEN-")}
        ledger_only = txn_ids - gl_ids
        gl_only = {g for g in (gl_ids - txn_ids - opening_ids)}

        mismatches = []
        for t in self.memory["txns"]:
            if t.id in gl_ids:
                expected = led["per_txn_value"][t.id]
                sign = 1.0 if (t.ttype == "receipt" or t.qty > 0) else -1.0
                diff = gl_amt[t.id] - sign * expected
                if abs(diff) > max(cfg.recon_tolerance_abs, 0.01 * abs(expected)):
                    mismatches.append({"txn": t.id, "sku": t.sku, "type": t.ttype,
                                       "date": t.date, "ledger_value": sign * expected,
                                       "gl_value": gl_amt[t.id], "diff": diff})

        self.memory["recon"] = {"rows": rows, "flagged": flagged, "ledger_only": ledger_only,
                                "gl_only": gl_only, "gl_only_amount": {g: gl_amt[g] for g in gl_only},
                                "mismatches": mismatches}

        for t in self.memory["txns"]:
            if t.id in ledger_only:
                self._finding("RECONCILIATION", "MEDIUM",
                              f"{t.ttype} {t.id} ({self._money(led['per_txn_value'][t.id])}) is in "
                              "the stock ledger but has no GL posting",
                              f"txn {t.id} dated {t.date} on {t.sku}",
                              "Post the missing journal (draft JE provided); review why the "
                              "ledger-to-GL interface failed")
        for gid in sorted(gl_only):
            self._finding("RECONCILIATION", "HIGH",
                          "GL inventory entry with no supporting stock movement",
                          f"GL reference {gid}",
                          "Investigate possible fictitious receipt or misposting; reverse if "
                          "unsupported (draft JE provided)")
        for m in mismatches:
            self._finding("RECONCILIATION", "HIGH",
                          "GL amount differs from the ledger valuation of the same transaction",
                          f"txn {m['txn']} ({m['type']}): ledger {m['ledger_value']:,.2f} vs "
                          f"GL {m['gl_value']:,.2f}",
                          "Correct the GL posting (draft JE provided)")
        self._log("RECONCILE", "stock-to-GL",
                  f"{len(flagged)} SKUs outside tolerance, {len(ledger_only)} unposted txns, "
                  f"{len(gl_only)} GL-only entries, {len(mismatches)} amount mismatches")

    # ---------- tool 4: anomaly detection ----------
    def tool_anomalies(self):
        cfg, led, txns = self.cfg, self.memory["ledger"], self.memory["txns"]
        n0 = len(self.findings)

        for code, mq in led["min_qty"].items():
            if mq < 0:
                self._finding("ANOMALY", "HIGH",
                              "Negative stock balance (issues exceed stock on hand)",
                              f"{code} reached {mq:,.0f} units on {led['min_qty_date'][code]}",
                              "Trace offending issue transactions; likely mis-keyed quantity or "
                              "unrecorded receipt; correct before close")

        adj = [t for t in txns if t.ttype == "adjustment"]
        vals = [led["per_txn_value"][t.id] for t in adj]
        if len(vals) >= 2 and statistics.stdev(vals) > 0:
            mu, sd = statistics.mean(vals), statistics.stdev(vals)
            for t in adj:
                v = led["per_txn_value"][t.id]
                if v > cfg.writeoff_hard_cap:
                    self._finding("ANOMALY", "HIGH",
                                  f"Write-off of {self._money(v)} exceeds the "
                                  f"{self._money(cfg.writeoff_hard_cap)} policy cap",
                                  f"txn {t.id} on {t.sku} dated {t.date}: '{t.note}'",
                                  "Obtain incident report and approval evidence; confirm any "
                                  "insurance recovery")
                elif v > mu + cfg.writeoff_sigma * sd:
                    self._finding("ANOMALY", "MEDIUM",
                                  f"Write-off {self._money(v)} is a statistical outlier "
                                  f"(> {cfg.writeoff_sigma} sigma)",
                                  f"txn {t.id} on {t.sku} dated {t.date}: '{t.note}'",
                                  "Review the supporting damage report")

        seen = defaultdict(list)
        for t in adj:
            seen[(t.sku, t.date, abs(t.qty))].append(t)
        for (code, d, q), group in seen.items():
            if len(group) > 1:
                ids = ", ".join(t.id for t in group)
                self._finding("ANOMALY", "MEDIUM",
                              f"Possible duplicate adjustment: {len(group)} identical write-offs "
                              f"of {q:.0f} units",
                              f"{code} on {d}: txns {ids}",
                              "Confirm with the warehouse whether two physical events occurred; "
                              "reverse the duplicate")

        for code, sizes in led["issue_sizes"].items():
            if len(sizes) >= 5 and statistics.stdev(sizes) > 0:
                mu, sd = statistics.mean(sizes), statistics.stdev(sizes)
                mx = max(sizes)
                if mx > mu + cfg.issue_sigma * sd and mx > 2 * mu:
                    self._finding("ANOMALY", "MEDIUM",
                                  f"Single issue of {mx:.0f} units far outside the normal range "
                                  f"for {code}",
                                  f"typical issue ~{mu:.1f} +/- {sd:.1f} units",
                                  "Verify pick list vs system quantity; possible mis-key or theft")

        self._log("DETECT", "anomaly scan", f"{len(self.findings) - n0} new findings")

    # ---------- tool 5: aging / NRV provision ----------
    def tool_nrv(self):
        cfg, led = self.cfg, self.memory["ledger"]
        end = self.memory["period_end"]
        buckets = defaultdict(lambda: {"items": [], "value": 0.0, "provision": 0.0})

        for code in self.memory["skus"]:
            q, v = led["qty_end"][code], led["value_end"][code]
            if q <= 0 or v <= 0:
                continue
            li = led["last_issue"].get(code)
            days = (end - li).days if li else cfg.window_days
            rate, cls = 0.0, "current"
            for name, (lo, hi, r) in cfg.provision_policy.items():
                if lo <= days < hi:
                    rate, cls = r, name
                    break
            buckets[cls]["items"].append({"sku": code, "qty": q, "value": v,
                                          "days_no_sale": days, "class": cls,
                                          "rate": rate, "provision": v * rate})
            buckets[cls]["value"] += v
            buckets[cls]["provision"] += v * rate

        total = sum(b["provision"] for b in buckets.values())
        n_aged = sum(len(buckets[k]["items"]) for k in buckets if k != "current")
        # In production, read the existing allowance balance from the GL.
        self.memory["nrv"] = {"buckets": dict(buckets), "total_provision": total,
                              "existing_allowance": 0.0}
        self._log("VALUATE", "NRV / obsolescence", f"recommended provision {self._money(total)}")
        if total > 0:
            self._finding("VALUATION", "MEDIUM",
                          f"Obsolescence provision of {self._money(total)} required under "
                          "written policy (IAS 2 / ASC 330 lower of cost and NRV)",
                          f"{n_aged} SKUs aged beyond policy thresholds",
                          "Review flagged SKUs with sales/ops; approve the write-down "
                          "(draft JE provided)")

    # ---------- tool 6: draft journals (never posts) ----------
    def _add_je(self, date_, lines, memo, source, reason, confidence):
        je = JournalEntry(f"JE-{len(self.journal_drafts) + 1:03d}", date_, lines, memo,
                          source, reason, confidence)
        self.journal_drafts.append(je)
        self._log("DRAFT", "journal entry", f"{je.je_id}: {memo}")
        return je

    def tool_draft_journals(self):
        cfg, rec, led = self.cfg, self.memory["recon"], self.memory["ledger"]
        end = self.memory["period_end"]

        for t in self.memory["txns"]:                      # missing postings
            if t.id in rec["ledger_only"] and t.ttype == "receipt":
                v = round(led["per_txn_value"][t.id], 2)
                self._add_je(end, [(f"Dr {cfg.accounts['inventory']}", v, 0.0),
                                   (f"Cr {cfg.accounts['ap']}", 0.0, v)],
                             f"Post unposted GRN {t.id} ({t.sku}) - verify supplier invoice",
                             "RECONCILIATION", "Stock receipt absent from GL", 0.95)

        for m in rec["mismatches"]:                        # wrong-amount postings
            delta = -round(m["diff"], 2)
            if abs(delta) < 0.01:
                continue
            t = next(t for t in self.memory["txns"] if t.id == m["txn"])
            counterpart = {"receipt": cfg.accounts["ap"], "issue": cfg.accounts["cogs"],
                           "adjustment": cfg.accounts["shrink"]}[t.ttype]
            lines = ([(f"Dr {cfg.accounts['inventory']}", delta, 0.0),
                      (f"Cr {counterpart}", 0.0, delta)] if delta > 0 else
                     [(f"Dr {counterpart}", -delta, 0.0),
                      (f"Cr {cfg.accounts['inventory']}", 0.0, -delta)])
            self._add_je(end, lines, f"Correct GL posting for {t.id} ({t.sku})",
                         "RECONCILIATION", "GL amount differs from ledger valuation", 0.90)

        for gid in sorted(rec["gl_only"]):                 # unsupported GL entries
            amt = round(rec["gl_only_amount"][gid], 2)
            self._add_je(end, [(f"Dr {cfg.accounts['ap']}", amt, 0.0),
                               (f"Cr {cfg.accounts['inventory']}", 0.0, amt)],
                         f"Reverse unsupported GL entry {gid} pending investigation",
                         "RECONCILIATION", "GL inventory debit with no stock movement", 0.60)

        total = round(self.memory["nrv"]["total_provision"], 2)
        if total > 0:
            self._add_je(end, [(f"Dr {cfg.accounts['writedown']}", total, 0.0),
                               (f"Cr {cfg.accounts['allowance']}", 0.0, total)],
                         "Obsolescence provision per NRV policy (item detail in report section 5)",
                         "VALUATION", "Slow/dead stock aged beyond policy thresholds", 0.80)

    # ---------- tool 7: report ----------
    def tool_report(self):
        led, rec, nrv, cfg = self.memory["ledger"], self.memory["recon"], \
            self.memory["nrv"], self.cfg
        L = w = (L := []).append
        total_ledger = sum(led["value_end"].values())
        total_gl = sum(r["gl_value"] for r in rec["rows"])
        flagged = rec["flagged"]
        high = [f for f in self.findings if f["severity"] == "HIGH"]

        w("# Inventory Integrity Agent - Close Report")
        w("")
        w(f"**Period:** {self.memory['period_start']} to {self.memory['period_end']}  ")
        w(f"**Generated:** {datetime.now():%Y-%m-%d %H:%M}  ")
        w(f"**Scope:** {len(self.memory['skus'])} SKUs | {len(self.memory['txns'])} stock "
          f"transactions | {len(self.memory['gl'])} GL lines")
        w("")
        w("## 1. Executive summary")
        w("")
        w(f"- Closing stock ledger value: **{self._money(total_ledger)}** "
          f"(GL inventory control: {self._money(total_gl)}, net variance "
          f"{self._money(total_ledger - total_gl)})")
        w(f"- {len(flagged)} SKUs reconciled outside tolerance")
        w(f"- {len(self.findings)} findings ({len(high)} high severity)")
        w(f"- Recommended obsolescence provision: **{self._money(nrv['total_provision'])}**")
        w(f"- Draft journals awaiting approval: **{len(self.journal_drafts)}** "
          f"(total movement {self._money(sum(sum(d for _, d, _ in je.lines)
                                              for je in self.journal_drafts))})")
        w("")
        w("## 2. Stock-to-GL reconciliation (exceptions only)")
        w("")
        if flagged:
            w("| SKU | Ledger qty | Ledger value | GL value | Variance |")
            w("|---|---:|---:|---:|---:|")
            for r in sorted(flagged, key=lambda x: -abs(x["variance"]))[:12]:
                w(f"| {r['sku']} | {r['qty']:,.0f} | {r['ledger_value']:,.2f} | "
                  f"{r['gl_value']:,.2f} | {r['variance']:,.2f} |")
        else:
            w("All SKUs within tolerance.")
        w("")
        w("## 3. Unmatched items and amount mismatches")
        w("")
        led_only = [t for t in self.memory["txns"] if t.id in rec["ledger_only"]]
        for t in led_only:
            w(f"- In stock ledger, NOT in GL: {t.ttype} `{t.id}` {t.date} {t.sku} "
              f"{self._money(led['per_txn_value'][t.id])} ({t.note})")
        for gid in sorted(rec["gl_only"]):
            w(f"- In GL with no stock movement: `{gid}` "
              f"{self._money(rec['gl_only_amount'][gid])}")
        for m in rec["mismatches"]:
            w(f"- Amount mismatch `{m['txn']}` ({m['type']}, {m['sku']}, {m['date']}): "
              f"ledger {m['ledger_value']:,.2f} vs GL {m['gl_value']:,.2f} "
              f"(diff {m['diff']:,.2f})")
        if not (led_only or rec["gl_only"] or rec["mismatches"]):
            w("None found.")
        w("")
        w("## 4. Anomaly & valuation register")
        w("")
        w("| ID | Severity | Finding | Recommended action |")
        w("|---|---|---|---|")
        for f in self.findings:
            if f["module"] in ("ANOMALY", "VALUATION"):
                w(f"| {f['id']} | {f['severity']} | {f['description']} | "
                  f"{f['recommended_action']} |")
        w("")
        w("## 5. Slow-moving stock & NRV provision (IAS 2 / ASC 330)")
        w("")
        rules = {"current": "no flag"}
        rules.update({k: f"{lo}-{hi if hi < 10**8 else '+'} days no sale @ {r:.0%}"
                      for k, (lo, hi, r) in cfg.provision_policy.items()})
        w("| Class | Policy rule | SKUs | Value | Provision |")
        w("|---|---|---:|---:|---:|")
        for cls in ["current", "slow", "dead", "obsolete"]:
            b = nrv["buckets"].get(cls)
            if b and b["items"]:
                w(f"| {cls} | {rules[cls]} | {len(b['items'])} | "
                  f"{b['value']:,.2f} | {b['provision']:,.2f} |")
        w("")
        items = sorted((i for b in nrv["buckets"].values() for i in b["items"]),
                       key=lambda x: -x["provision"])[:10]
        w("Largest exposures:")
        w("")
        w("| SKU | Qty | Value | Days no sale | Class | Provision |")
        w("|---|---:|---:|---:|---|---:|")
        for i in items:
            w(f"| {i['sku']} | {i['qty']:,.0f} | {i['value']:,.2f} | "
              f"{i['days_no_sale']} | {i['class']} | {i['provision']:,.2f} |")
        w("")
        w("## 6. Draft journal entries - REQUIRE APPROVAL")
        w("")
        w("> The agent never posts. Every journal below must be approved by the "
          "inventory controller before entry into the ledger (segregation of duties).")
        w("")
        for je in self.journal_drafts:
            w(f"**{je.je_id}** - {je.memo}  ")
            w(f"Source: {je.source} | Confidence: {je.confidence:.0%} | Status: {je.status}  ")
            w("")
            w("| Account | Debit | Credit |")
            w("|---|---:|---:|")
            for acct, d, c in je.lines:
                w(f"| {acct} | {d:,.2f} | {c:,.2f} |")
            w("")
        w("## 7. Recommended actions")
        w("")
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for n, f in enumerate(sorted(self.findings, key=lambda x: order[x["severity"]]), 1):
            w(f"{n}. **[{f['severity']}]** {f['recommended_action']} - *{f['description']}*")
        w("")
        w("## 8. Agent control statement & audit trail")
        w("")
        w("Deterministic rules and statistics were used (no opaque model output) so every "
          "number above is reproducible and auditable. Recent run log:")
        w("")
        w("```")
        for e in self.audit_log[-10:]:
            w(f"{e['ts']}  {e['step']:<10} {e['action']:<18} {e['detail']}")
        w("```")
        report = "\n".join(L)
        payload = {
            "summary": {"ledger_value": total_ledger, "gl_value": total_gl,
                        "skus_flagged": len(flagged), "findings": len(self.findings),
                        "high_severity": len(high),
                        "provision_recommended": nrv["total_provision"],
                        "draft_journals": len(self.journal_drafts)},
            "findings": self.findings,
            "journal_drafts": [asdict(j) for j in self.journal_drafts],
            "reconciliation_flagged": flagged,
            "nrv": {"total_provision": nrv["total_provision"], "buckets": nrv["buckets"]},
            "audit_log": self.audit_log,
        }
        return report, payload

    # ---------- orchestration ----------
    def run(self, data):
        self._log("PLAN", "orchestration",
                  "ingest -> replay -> reconcile -> detect -> valuate -> draft -> report")
        self.tool_ingest(data)
        self.tool_replay()
        self.tool_reconcile()
        self.tool_anomalies()
        self.tool_nrv()
        self.tool_draft_journals()
        self._log("REPORT", "emit", "markdown + json written")
        return self.tool_report()


# ----------------------------------------------------------------------------
def main():
    print("=" * 74)
    print(" INVENTORY INTEGRITY AGENT - demo run (synthetic ERP data, seeded errors)")
    print("=" * 74)
    cfg = Config()
    world = build_demo_world(cfg)
    valuation = replay_stock_ledger(world["skus"], world["txns"])   # ERP valuation pass
    gl = build_gl_export(world, cfg, valuation["per_txn_value"])    # GL export w/ errors

    agent = InventoryIntegrityAgent(cfg)
    report, payload = agent.run({"skus": world["skus"], "txns": world["txns"], "gl": gl,
                                 "period_start": world["period_start"],
                                 "period_end": world["period_end"]})
    print(report)
    with open("iia_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    with open("iia_report.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print("\nFiles written: iia_report.md, iia_report.json")


if __name__ == "__main__":
    main()
