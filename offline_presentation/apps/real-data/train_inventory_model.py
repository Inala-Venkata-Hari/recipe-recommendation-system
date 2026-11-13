"""Reproducible synthetic-outcome experiment; not evidence of real-world sales uplift."""
import argparse,json
from pathlib import Path
import numpy as np
from ml_inventory import fit_model,predict_risk,MODEL_PATH

def generate(seed=42,products=180,episodes=60):
    rng=np.random.default_rng(seed);rows=[];targets=[];groups=[]
    for product in range(products):
        demand=rng.uniform(.3,18);frequency=rng.uniform(0,.6)
        for episode in range(episodes):
            stock=int(rng.integers(10,220));remaining=int(rng.integers(1,22));age=int(rng.integers(0,31));target=int(rng.integers(5,30))
            observed_sales=max(0,demand*rng.lognormal(0,.18))
            # A stochastic outcome-generating assumption, independent of current score weights.
            freshness=np.exp(-.12*age/target)
            future_sales=rng.poisson(demand*min(remaining,7)*freshness*(.85+.3*frequency))
            sold=min(stock,int(future_sales));unsold=(stock-sold)/stock
            row=dict(stock_qty=stock,avg_daily_sales=observed_sales,days_remaining=remaining,days_in_stock=age,target_holding_days=target,frequency_ratio=frequency)
            # Missing historical signals are realistic input variation, not invented observed values.
            if rng.random()<.08:row['avg_daily_sales']=None
            if rng.random()<.04:row['days_remaining']=None
            if rng.random()<.05:row['frequency_ratio']=None
            rows.append(row);targets.append(unsold);groups.append(product)
    return rows,np.asarray(targets),np.asarray(groups)

def train(output=MODEL_PATH):
    rows,y,groups=generate();train_mask=groups<126;valid_mask=(groups>=126)&(groups<153);test_mask=groups>=153
    training=[r for r,m in zip(rows,train_mask) if m]
    model=fit_model(training,y[train_mask]);baseline=float(y[train_mask].mean())
    report={}
    for label,mask in [('validation',valid_mask),('test',test_mask)]:
        actual=y[mask];pred=predict_risk([r for r,m in zip(rows,mask) if m],model)
        report[label]=dict(rows=int(mask.sum()),mae=float(np.mean(abs(actual-pred))),rmse=float(np.sqrt(np.mean((actual-pred)**2))),constant_baseline_mae=float(np.mean(abs(actual-baseline))),constant_baseline_rmse=float(np.sqrt(np.mean((actual-baseline)**2))))
    model.update(training_origin='SYNTHETIC simulated batch sales outcomes; not observed retailer sales',target='Fraction of initial stock unsold after min(days to expiry, 7) days at unchanged price',seed=42,training_rows=int(train_mask.sum()),split='Product-disjoint 70% training / 15% validation / 15% test; no product overlap',evaluation=report,limitations=['Simulation assumptions determine the learned relationship.','No causal price elasticity or optimal discount is learned.','Discount percentage still uses seller maximum and margin constraints.','Missing expiry uses a seven-day horizon.','Real sales data and temporal validation are required before operational use.'])
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(model,indent=2))
    print(json.dumps(report,indent=2));print('Saved',output)
    return model
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=MODEL_PATH);args=parser.parse_args();train(args.output)
