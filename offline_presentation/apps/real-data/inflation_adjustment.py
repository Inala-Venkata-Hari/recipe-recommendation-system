"""Pinned official CPI snapshot; approximate USD purchasing-power adjustment."""
import math

SNAPSHOT={
    'series':'CUUR0000SA0',
    'description':'US CPI-U, all items, not seasonally adjusted',
    'base_period':'2017–2018 annual-average midpoint',
    'base_index':(245.120+251.107)/2,
    'target_period':'September 2026',
    'target_index':336.940,
    'verified_on':'2026-11-08',
    'source_url':'https://www.bls.gov/news.release/archives/cpi_10142026.htm',
    'base_source_url':'https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm',
}


def inflation_reference(reference,enabled=True,snapshot=None):
    """Always start from original source rates; never compound previous adjustments."""
    snapshot=snapshot or SNAPSHOT
    base=float(snapshot['base_index']);target=float(snapshot['target_index'])
    if not all(math.isfinite(v) and v>0 for v in [base,target]):
        raise ValueError('CPI indexes must be finite and positive.')
    result=reference.copy()
    result['source_price_per_100g_usd']=reference.get('source_price_per_100g_usd',reference.price_per_100g_usd)
    result['inflation_factor']=target/base if enabled else 1.0
    result['price_per_100g_usd']=result.source_price_per_100g_usd*result.inflation_factor
    result['reference_price_basis']=(f"CPI-adjusted estimate ({snapshot['target_period']})" if enabled else 'USDA historical estimate')
    return result
