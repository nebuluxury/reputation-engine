#!/usr/bin/env python3
"""Reputation Engine - financial model. Produces exact projection numbers as JSON."""
import json

# ---- Assumptions (base case) ----
WORKING_DAYS = 22
CARD_PRICE   = 5      # what a reseller pays us per card
CARD_COGS    = 3      # our cost incl. shipping
CARD_MARGIN  = CARD_PRICE - CARD_COGS   # 2
SUB_PRICE    = 15     # monthly subscription
INFRA_SUB    = 2      # Stripe + SMS + hosting per active sub/month
SUB_NET      = SUB_PRICE - INFRA_SUB    # 13 company net per collected sub-month
ATTACH       = 0.40   # % of card buyers who take the $15/mo
CHURN        = 0.06   # monthly subscription churn
RESELLER_RETAIL = 40  # what reseller charges the business per card
REP_CARD_SPREAD = RESELLER_RETAIL - CARD_PRICE  # 35 to rep

# 12-month salesperson headcount ramp (illustrative growth scenario)
HEADCOUNT = [3, 6, 15, 20, 30, 50, 70, 100, 150, 250, 375, 500]

SALES_PER_DAY = [1, 3, 5, 10]

def run(sales_per_day, attach=ATTACH, churn=CHURN, headcount=HEADCOUNT):
    months = len(headcount)
    cards_per_rep = sales_per_day * WORKING_DAYS
    cohorts = []  # each: {'active': float, 'age': int}  age in months since signup
    rows = []
    cum_cards = 0
    cum_company_gross = 0
    cum_rep_earnings = 0
    for m in range(months):
        # age existing cohorts + churn
        for c in cohorts:
            c['age'] += 1
            c['active'] *= (1 - churn)
        cards = headcount[m] * cards_per_rep
        cum_cards += cards
        new_subs = cards * attach
        cohorts.append({'active': new_subs, 'age': 1})

        # company subscription revenue: cohorts with age >= 3 (months 1-2 go to rep)
        company_sub_active = sum(c['active'] for c in cohorts if c['age'] >= 3)
        rep_sub_active     = sum(c['active'] for c in cohorts if c['age'] <= 2)
        total_active       = sum(c['active'] for c in cohorts)

        company_card_rev = cards * CARD_MARGIN
        company_sub_rev  = company_sub_active * SUB_NET
        company_gross    = company_card_rev + company_sub_rev
        cum_company_gross += company_gross

        # rep earnings this month: card spread on new cards + $15 on subs in month 1-2 of life
        rep_card = cards * REP_CARD_SPREAD
        rep_sub  = rep_sub_active * SUB_PRICE
        rep_earn = rep_card + rep_sub
        cum_rep_earnings += rep_earn

        rows.append({
            'month': m + 1,
            'reps': headcount[m],
            'cards': round(cards),
            'cum_cards': round(cum_cards),
            'new_subs': round(new_subs),
            'active_subs': round(total_active),
            'company_card_rev': round(company_card_rev),
            'company_sub_rev': round(company_sub_rev),
            'company_gross': round(company_gross),
            'cum_company_gross': round(cum_company_gross),
            'mrr': round(company_sub_active * SUB_PRICE),  # gross MRR company is collecting
            'rep_earn_total_all_reps': round(rep_earn),
            'rep_earn_per_rep': round(rep_earn / headcount[m]) if headcount[m] else 0,
        })
    return rows

out = {
    'assumptions': {
        'working_days': WORKING_DAYS, 'card_price': CARD_PRICE, 'card_cogs': CARD_COGS,
        'card_margin': CARD_MARGIN, 'sub_price': SUB_PRICE, 'infra_sub': INFRA_SUB,
        'sub_net': SUB_NET, 'attach': ATTACH, 'churn': CHURN,
        'reseller_retail': RESELLER_RETAIL, 'rep_card_spread': REP_CARD_SPREAD,
        'headcount': HEADCOUNT,
    },
    'scenarios': {}
}
for spd in SALES_PER_DAY:
    out['scenarios'][spd] = run(spd)

# Sensitivity: base case (3/day) under attach & churn variations, 12-month cum gross + M12 MRR
sens = {}
for att in [0.25, 0.40, 0.55]:
    for ch in [0.04, 0.06, 0.10]:
        rows = run(3, attach=att, churn=ch)
        sens[f'attach{int(att*100)}_churn{int(ch*100)}'] = {
            'cum_company_gross_12mo': rows[-1]['cum_company_gross'],
            'mrr_m12': rows[-1]['mrr'],
            'active_subs_m12': rows[-1]['active_subs'],
        }
out['sensitivity_3perday'] = sens

print(json.dumps(out, indent=2))
