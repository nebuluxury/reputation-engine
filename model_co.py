#!/usr/bin/env python3
"""Colombia operator model - card-sale economics + salesperson daily earnings."""
import json

WORKING_DAYS = 24          # Colombia often 6-day weeks
SALE_PRICE   = 30          # USD charged to the business per card
CARD_COST    = 2           # hardware cost, paid by operator
COMMISSION_A = 20          # salesperson commission (Model A - his example)
# Operator net per sale, Model A: 30 - 20 - 2 = 8
OP_NET_A     = SALE_PRICE - COMMISSION_A - CARD_COST      # 8
# Model B: split the $28 profit 50/50 -> $14 each; operator already paid card
PROFIT       = SALE_PRICE - CARD_COST                     # 28
COMMISSION_B = 14
OP_NET_B     = 14
USD_COP      = 4000        # approximate; stated as assumption

SALES_PER_DAY = [1, 3, 5, 10]
# realistic single-city operator ramp of salespeople over 12 months
RAMP = [1, 2, 3, 5, 8, 12, 15, 20, 25, 30, 40, 50]

def salesperson_table():
    rows = []
    for s in SALES_PER_DAY:
        per_day_A = s * COMMISSION_A
        per_mo_A  = s * WORKING_DAYS * COMMISSION_A
        per_day_B = s * COMMISSION_B
        per_mo_B  = s * WORKING_DAYS * COMMISSION_B
        rows.append({'spd': s, 'per_day_A': per_day_A, 'per_mo_A': per_mo_A,
                     'per_day_B': per_day_B, 'per_mo_B': per_mo_B})
    return rows

def operator_projection(op_net):
    out = {}
    for s in SALES_PER_DAY:
        cum = 0; series = []
        for m in range(12):
            cards = RAMP[m] * s * WORKING_DAYS
            profit = cards * op_net
            cum += profit
            series.append({'month': m+1, 'reps': RAMP[m], 'cards': cards,
                           'profit': profit, 'cum': cum})
        out[s] = series
    return out

data = {
    'params': {'working_days': WORKING_DAYS, 'sale_price': SALE_PRICE, 'card_cost': CARD_COST,
               'commission_A': COMMISSION_A, 'op_net_A': OP_NET_A,
               'commission_B': COMMISSION_B, 'op_net_B': OP_NET_B, 'usd_cop': USD_COP,
               'ramp': RAMP},
    'salesperson': salesperson_table(),
    'operator_A': operator_projection(OP_NET_A),
    'operator_B': operator_projection(OP_NET_B),
}

# print summary
print("=== SALESPERSON EARNINGS (Model A $20 / Model B $14 commission) ===")
for r in data['salesperson']:
    print(f"  {r['spd']:>2}/day: A ${r['per_day_A']}/day ${r['per_mo_A']}/mo  |  B ${r['per_day_B']}/day ${r['per_mo_B']}/mo")

for label, key, net in [("MODEL A (op nets $8/sale)","operator_A",OP_NET_A),
                         ("MODEL B (op nets $14/sale)","operator_B",OP_NET_B)]:
    print(f"\n=== OPERATOR CUMULATIVE PROFIT - {label} ===")
    print("  sales/day |  M1  |  M3  |  M6  |  M9  |  M12  (cumulative USD)")
    for s in SALES_PER_DAY:
        ser = data[key][s]
        pick = {m['month']: m['cum'] for m in ser}
        print(f"    {s:>2}/day  | ${pick[1]:>6,} | ${pick[3]:>7,} | ${pick[6]:>7,} | ${pick[9]:>8,} | ${pick[12]:>9,}")

json.dump(data, open('model_co_output.json','w'), indent=2)
print("\nsaved model_co_output.json")
