#!/usr/bin/env python3
"""Reputation Engine - financial model v2 ($50 pricing). Exact projection numbers."""
import json

# ---- Assumptions (base case, $50 pricing) ----
WORKING_DAYS = 22
CARD_RETAIL  = 50     # what the business pays
REP_COMMISSION = 30   # rep keeps per card
CARD_COST    = 2      # our hardware + ship
CARD_NET     = CARD_RETAIL - REP_COMMISSION - CARD_COST   # 18 company net per card
SUB_PRICE    = 15     # monthly subscription
REP_RESIDUAL = 5      # paid to rep per active sub/month for 12 months
SUB_INFRA    = 2      # Stripe + SMS + hosting per active sub/month
SUB_NET      = SUB_PRICE - REP_RESIDUAL - SUB_INFRA       # 8 company net per active sub-month
ATTACH       = 0.25   # % of card buyers who take the $15/mo plan
CHURN        = 0.06   # monthly subscription churn

HEADCOUNT = [3, 6, 15, 20, 30, 50, 70, 100, 150, 250, 375, 500]
SALES_PER_DAY = [1, 3, 5, 10]

def run(sales_per_day, attach=ATTACH, churn=CHURN, headcount=HEADCOUNT):
    months = len(headcount)
    cards_per_rep = sales_per_day * WORKING_DAYS
    cohorts = []
    rows = []
    cum_cards = 0; cum_company = 0; cum_rep = 0
    for m in range(months):
        for c in cohorts:
            c['age'] += 1
            c['active'] *= (1 - churn)
        cards = headcount[m] * cards_per_rep
        cum_cards += cards
        new_subs = cards * attach
        cohorts.append({'active': new_subs, 'age': 1})
        active = sum(c['active'] for c in cohorts)

        card_profit = cards * CARD_NET
        sub_profit  = active * SUB_NET          # company net (rep residual within 12mo)
        company     = card_profit + sub_profit
        cum_company += company
        mrr_gross   = active * SUB_PRICE        # total recurring revenue generated
        rep_earn    = cards * REP_COMMISSION + active * REP_RESIDUAL
        cum_rep    += rep_earn

        rows.append({
            'month': m+1, 'reps': headcount[m], 'cards': round(cards), 'cum_cards': round(cum_cards),
            'new_subs': round(new_subs), 'active_subs': round(active),
            'card_profit': round(card_profit), 'sub_profit': round(sub_profit),
            'company': round(company), 'cum_company': round(cum_company),
            'mrr_gross': round(mrr_gross), 'rep_per_rep': round(rep_earn/headcount[m]) if headcount[m] else 0,
        })
    return rows

out = {'assumptions': {'working_days':WORKING_DAYS,'card_retail':CARD_RETAIL,'rep_commission':REP_COMMISSION,
    'card_cost':CARD_COST,'card_net':CARD_NET,'sub_price':SUB_PRICE,'rep_residual':REP_RESIDUAL,
    'sub_infra':SUB_INFRA,'sub_net':SUB_NET,'attach':ATTACH,'churn':CHURN,'headcount':HEADCOUNT},
    'scenarios':{}}
for spd in SALES_PER_DAY:
    out['scenarios'][spd] = run(spd)

sens = {}
for att in [0.15,0.25,0.40]:
    for ch in [0.04,0.06,0.10]:
        rows = run(3, attach=att, churn=ch)
        sens[f'a{int(att*100)}_c{int(ch*100)}'] = rows[-1]['cum_company']
out['sensitivity_3'] = sens

# ---- print ----
a=out['assumptions']
print("ASSUMPTIONS:", json.dumps(a))
print("\n== S6 TABLE1 cumulative company profit ==")
for spd in [1,3,5,10]:
    r=out['scenarios'][spd]; p={m['month']:m['cum_company'] for m in r}
    print(f"{spd}/day: M1 ${p[1]:,} | M3 ${p[3]:,} | M6 ${p[6]:,} | M9 ${p[9]:,} | M12 ${p[12]:,}")
print("\n== S6 TABLE2 at M12 ==")
for spd in [1,3,5,10]:
    r=out['scenarios'][spd][-1]
    print(f"{spd}/day: cards {r['cum_cards']:,} | active {r['active_subs']:,} | MRR ${r['mrr_gross']:,} | annual ${r['mrr_gross']*12:,}")
print("\n== S7 month-by-month 3/day ==")
for m in out['scenarios'][3]:
    print(f"M{m['month']}|reps {m['reps']}|cards {m['cards']:,}|new {m['new_subs']:,}|active {m['active_subs']:,}|cardP ${m['card_profit']:,}|subP ${m['sub_profit']:,}|co ${m['company']:,}|cum ${m['cum_company']:,}|rep/rep ${m['rep_per_rep']:,}")
print("\n== S8 sensitivity (3/day, yr1 cum company) ==")
for k,v in out['sensitivity_3'].items(): print(f"{k}: ${v:,}")
json.dump(out, open('model_output.json','w'))
