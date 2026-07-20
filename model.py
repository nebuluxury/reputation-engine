#!/usr/bin/env python3
"""Reputation Engine - financial model v3 ($50 pricing, 36 months, exit valuation)."""
import json

WORKING_DAYS = 22
CARD_RETAIL  = 50
REP_COMMISSION = 30
CARD_COST    = 2
CARD_NET     = CARD_RETAIL - REP_COMMISSION - CARD_COST   # 18
SUB_PRICE    = 15
REP_RESIDUAL = 5      # paid to rep per active sub/month for first 12 months
SUB_INFRA    = 2
SUB_NET_Y1   = SUB_PRICE - REP_RESIDUAL - SUB_INFRA       # 8  (sub age <=12)
SUB_NET_Y2   = SUB_PRICE - SUB_INFRA                      # 13 (sub age >12, rep residual ended)
ATTACH       = 0.25
CHURN        = 0.06

# 36-month salesforce ramp (Y1 to 500, decelerating growth after)
HEADCOUNT = [3,6,15,20,30,50,70,100,150,250,375,500,
             560,620,680,740,800,850,900,940,970,1000,1030,1060,
             1090,1120,1150,1180,1210,1240,1270,1300,1330,1360,1390,1420]
SALES_PER_DAY = [1,3,5,10]

def run(spd, attach=ATTACH, churn=CHURN, headcount=HEADCOUNT):
    cards_per_rep = spd*WORKING_DAYS
    cohorts=[]; rows=[]; cum_cards=0; cum_company=0
    for m in range(len(headcount)):
        for c in cohorts:
            c['age']+=1; c['active']*=(1-churn)
        cards=headcount[m]*cards_per_rep; cum_cards+=cards
        new_subs=cards*attach; cohorts.append({'active':new_subs,'age':1})
        active=sum(c['active'] for c in cohorts)
        # company subscription profit: $8/mo while rep residual runs (age<=12), $13 after
        sub_profit=sum(c['active']*(SUB_NET_Y1 if c['age']<=12 else SUB_NET_Y2) for c in cohorts)
        card_profit=cards*CARD_NET
        company=card_profit+sub_profit; cum_company+=company
        mrr_gross=active*SUB_PRICE
        rows.append({'month':m+1,'reps':headcount[m],'cards':round(cards),'cum_cards':round(cum_cards),
            'new_subs':round(new_subs),'active_subs':round(active),'card_profit':round(card_profit),
            'sub_profit':round(sub_profit),'company':round(company),'cum_company':round(cum_company),
            'mrr_gross':round(mrr_gross)})
    return rows

scen={spd:run(spd) for spd in SALES_PER_DAY}

def at(spd,m): return scen[spd][m-1]

print("== cumulative company profit ==")
for spd in SALES_PER_DAY:
    print(f"{spd}/day: M12 ${at(spd,12)['cum_company']:,} | M24 ${at(spd,24)['cum_company']:,} | M36 ${at(spd,36)['cum_company']:,}")

print("\n== base 3/day snapshots ==")
for m in [12,24,36]:
    r=at(3,m)
    print(f"M{m}: reps {r['reps']} | active {r['active_subs']:,} | grossMRR ${r['mrr_gross']:,} | subProfit/mo ${r['sub_profit']:,} | totalProfit/mo ${r['company']:,} | cum ${r['cum_company']:,}")

# exit metrics at M36, base 3/day
r36=at(3,36)
arr_gross=r36['mrr_gross']*12
rec_profit_yr=r36['sub_profit']*12           # recurring subscription profit run-rate
total_profit_yr=r36['company']*12            # total profit run-rate incl card sales
print("\n== EXIT @ 36 months (3/day base) ==")
print(f"Active subscribers: {r36['active_subs']:,}")
print(f"Gross MRR: ${r36['mrr_gross']:,}  |  ARR (gross recurring rev): ${arr_gross:,}")
print(f"Recurring PROFIT run-rate/yr: ${rec_profit_yr:,}")
print(f"Total profit run-rate/yr (incl cards): ${total_profit_yr:,}")
print("Valuation on ARR multiple:")
for x in [3,4,5,6]:
    print(f"  {x}x ARR = ${arr_gross*x:,}")
print("Valuation on profit multiple (recurring profit run-rate):")
for x in [4,5,6,8]:
    print(f"  {x}x = ${rec_profit_yr*x:,}")

json.dump({'scen':scen,'assump':{'card_net':CARD_NET,'sub_net_y1':SUB_NET_Y1,'sub_net_y2':SUB_NET_Y2,
    'attach':ATTACH,'churn':CHURN,'headcount':HEADCOUNT}}, open('model_output.json','w'))
