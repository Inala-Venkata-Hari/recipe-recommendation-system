"""Learn expected unsold fraction from batch outcomes using fractional logistic regression.

The bundled artifact is trained on simulated outcomes, not real retailer observations.
No existing heuristic score is used as a training target.
"""
import json
from pathlib import Path
import numpy as np

MODEL_PATH=Path(__file__).parent/'models/inventory_risk.json'
FEATURES=['log_stock','log_daily_sales','horizon_days','age_over_target','frequency_ratio','sales_missing','expiry_missing','frequency_missing']

def feature_matrix(rows):
    values=[]
    for row in rows:
        def number(key,default):
            try:v=float(row.get(key,default))
            except (ValueError,TypeError):return default
            return v if np.isfinite(v) else default
        stock=max(0,number('stock_qty',0));sales=number('avg_daily_sales',-1)
        remaining=number('days_remaining',-1);frequency=number('frequency_ratio',-1)
        horizon=min(max(remaining,0),7) if remaining>=0 else 7
        age=max(0,number('days_in_stock',0));target=max(1,number('target_holding_days',7))
        values.append([np.log1p(stock),np.log1p(max(0,sales)),horizon,min(age/target,5),max(0,frequency),float(sales<0),float(remaining<0),float(frequency<0)])
    return np.asarray(values,dtype=float).reshape((-1,len(FEATURES)))

def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-35,35)))

def fit_model(rows,targets,iterations=80):
    x=feature_matrix(rows);y=np.asarray(targets,dtype=float)
    if len(y)!=len(x) or len(y)<50 or not np.isfinite(y).all() or np.any((y<0)|(y>1)):
        raise ValueError('Need at least 50 matching outcomes between zero and one.')
    mean=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-8]=1
    design=np.column_stack([np.ones(len(x)),(x-mean)/scale]);weights=np.zeros(design.shape[1])
    penalty=np.eye(len(weights))*.5;penalty[0,0]=0
    for _ in range(iterations):
        p=sigmoid(design@weights);gradient=design.T@(p-y)+penalty@weights
        hessian=design.T@((p*(1-p))[:,None]*design)+penalty+np.eye(len(weights))*1e-7
        step=np.linalg.solve(hessian,gradient);weights-=step
        if np.max(np.abs(step))<1e-7:break
    return dict(schema_version=1,algorithm='L2-regularized fractional logistic regression',features=FEATURES,mean=mean.tolist(),scale=scale.tolist(),coefficients=weights.tolist())

def predict_risk(rows,model):
    if model['features']!=FEATURES:raise ValueError('Incompatible ML feature schema.')
    x=(feature_matrix(rows)-np.asarray(model['mean']))/np.asarray(model['scale'])
    return sigmoid(np.column_stack([np.ones(len(x)),x])@np.asarray(model['coefficients']))

def load_model(path=None):
    source=Path(path or MODEL_PATH)
    if not source.exists():raise ValueError('Train the ML model first: python train_inventory_model.py')
    return json.loads(source.read_text())
