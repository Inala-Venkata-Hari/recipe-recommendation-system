"""Full USD demonstration workflow for the exactly code-joined USDA datasets."""
import hashlib
import io
import json
import os
from pathlib import Path
from datetime import date,timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from build_usda_trial import rank_formulations
from usda_workflow import (INVENTORY_COLUMNS,save_frame,load_inventory,frequency_table,effective_catalog,
    validate_price_upload,priced_formulations,inventory_upload,simulated_batches,draft_offers,
    customer_lines,schedule_fit,offer_schedule_matches,custom_formulation,validate_inventory_edits)
from usda_workflow import batch_pack_grams,recipe_availability,pack_price_rate,purchase_plan,one_serving_formulation
from cart_categories import CATEGORIES,product_category,recipe_cart_codes
from inflation_adjustment import SNAPSHOT,inflation_reference
from checkout import best_missing_combos,relevant_recipe_offers
from inventory_batches import create_batch
from inventory_discounts import classification_parameters
from offer_publishing import (promotion_id,publish_snapshot,active_promotions,save_promotions,
    load_promotions,promotion_history,record_promotion_changes,browse_promotions)
from invoice import render_invoice

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('USDA_DATA_DIR',str(ROOT/'data/usda_trial')))
WORK=Path(os.environ.get('USDA_WORK_DIR',str(DATA/'workspace')))
DEFAULT_DATE=date(2026,11,8)
st.set_page_config(page_title='Smart Cart | USDA workflow',page_icon='🥣',layout='wide')
st.title('🥣 Smart Cart — USDA workflow')
st.caption('Exactly linked food codes • prices and calories • customer/seller demonstration in USD')
if not (DATA/'manifest.json').exists():
    st.info('Import the USDA profile first.');st.code('python build_usda_trial.py --download');st.stop()

@st.cache_data
def load_data(path,stamp):
    folder=Path(path)
    return pd.read_csv(folder/'food_catalog.csv'),json.loads((folder/'formulations.json').read_text()),json.loads((folder/'manifest.json').read_text())

def read_frame(path,columns):
    return pd.read_csv(path) if Path(path).exists() else pd.DataFrame(columns=columns)

def read_menu():
    return json.loads((WORK/'menu_context.json').read_text()) if (WORK/'menu_context.json').exists() else {}

reference,source_formulations,manifest=load_data(str(DATA),(DATA/'manifest.json').stat().st_mtime_ns)
overrides=read_frame(WORK/'seller_prices.csv',['food_code','selling_price_per_100g_usd'])
inflation_enabled=st.sidebar.checkbox('Adjust historical USD estimates for inflation',value=True,key='usda_inflation')
adjusted_reference=inflation_reference(reference,inflation_enabled)
catalog=effective_catalog(adjusted_reference,overrides)
custom_records=json.loads((WORK/"custom_formulations.json").read_text()) if (WORK/"custom_formulations.json").exists() else []
menu=read_menu()
portion_grams=st.sidebar.number_input('Estimated ingredient weight for one serving (g)',min_value=1.0,value=300.0,step=25.0,key='usda_portion_grams')
st.sidebar.caption('Used when no seller serving count is declared. This is an input-weight estimate, not a USDA serving size or cooked yield.')
formulations=[one_serving_formulation(f,menu.get(str(f['food_code']),{}).get('servings'),portion_grams)
              for f in priced_formulations(source_formulations+custom_records,catalog)]
lookup={int(row['food_code']):row for row in catalog.to_dict('records')}
category_overrides=read_frame(WORK/'product_categories.csv',['food_code','category'])
override_lookup={int(r['food_code']):r['category'] for r in category_overrides.to_dict('records')}
pack_frame=read_frame(WORK/'pack_sizes.csv',['food_code','pack_size_g'])
pack_sizes={int(r['food_code']):float(r['pack_size_g']) for r in pack_frame.to_dict('records')}
categories={code:product_category(row['name'],override_lookup.get(code)) for code,row in lookup.items()}
formulation_lookup={int(f['food_code']):f for f in formulations}
classified=frequency_table(formulations)
menu=read_menu()
example_codes=list(formulation_lookup)
default_example=next((i for i,c in enumerate(example_codes) if formulation_lookup[c]['name']=='Beans and brown rice'),0)


def name_for(code):return lookup[int(code)]['name']
def offer_title(offer):return offer.get('display_name',' + '.join(name_for(c) for c in offer['items']))
def clear_receipt():
    st.session_state.pop('usda_receipt',None);st.session_state.pop('usda_receipt_fingerprint',None)

def choose_example(code):
    record=formulation_lookup[int(code)]
    st.session_state['usda_selected']=[int(i['food_code']) for i in record['ingredients']]
    st.session_state['usda_chosen_combos']=[]
    for item in record['ingredients']:st.session_state[f"usda_grams_{item['food_code']}"]=float(item['grams'])
    clear_receipt()

def add_combo(offer):
    chosen=st.session_state.get('usda_chosen_combos',[])
    occupied={c for saved in chosen for c in saved['items']}
    if occupied.intersection(offer['items']):
        st.session_state['usda_notice']='Remove the overlapping combo first.';return
    selected=list(st.session_state.get('usda_selected',[]))
    for code in offer['items']:
        code=int(code)
        if code not in selected:selected.append(code)
        key=f'usda_grams_{code}'
        st.session_state[key]=max(float(offer.get('quantities_g',{}).get(str(code),100)),float(st.session_state.get(key,0)))
    st.session_state['usda_selected']=selected
    st.session_state['usda_chosen_combos']=chosen+[offer]
    clear_receipt()

def add_missing(code,active,inventory):
    record=formulation_lookup[int(code)];selected=list(st.session_state.get('usda_selected',[]))
    missing=[]
    for item in record['ingredients']:
        code=int(item['food_code'])
        if code not in selected:
            selected.append(code);missing.append(str(code));st.session_state[f'usda_grams_{code}']=float(item['grams'])
    st.session_state['usda_selected']=selected
    required=[str(i['food_code']) for i in record['ingredients']]
    useful=relevant_recipe_offers(required,missing,active)
    for offer in best_missing_combos(required,useful,inventory,st.session_state.get('usda_chosen_combos',[])):add_combo(offer)
    clear_receipt()

def remove_combo(index):
    st.session_state['usda_chosen_combos'].pop(index);clear_receipt()

def clear_cart():
    for key in list(st.session_state):
        if key.startswith('usda_grams_') or key in {'usda_selected','usda_chosen_combos','usda_notice'}:
            del st.session_state[key]
    clear_receipt()

def reset_trial():
    for key in list(st.session_state):
        if key.startswith('usda_'):del st.session_state[key]

st.sidebar.button('Reset USDA trial',on_click=reset_trial)
st.sidebar.caption('Clears this session’s cart, receipt and controls. Saved inventory, seller prices, menu details and publications remain.')
a,b,c=st.columns(3)
a.metric('Foods with prices + calories',len(catalog));b.metric('Fully ingredient-priced formulations',len(formulations))
c.metric('Distinct priced ingredients used',classified.ingredient_name.nunique())
st.caption(f'{len(source_formulations)} USDA formulations + {len(custom_records)} saved user-entered component meals.')
st.info('USDA source prices are 2017–2018 national-average USD estimates, including imputed values. Inflation adjustment, when enabled, is an approximate update—not a live retail quote. Components may be cooked/packaged foods; survey formulations are not a raw-ingredient recipe collection.')
if inflation_enabled:
    factor=SNAPSHOT['target_index']/SNAPSHOT['base_index']
    st.caption(f"US all-items CPI snapshot: {SNAPSHOT['target_period']}; cumulative adjustment +{(factor-1)*100:.2f}% from the 2017–2018 average. Verified {SNAPSHOT['verified_on']}. Seller-entered prices and procurement costs are unchanged. This broad index does not track individual food prices.")
    st.link_button('Official inflation source',SNAPSHOT['source_url'])
st.caption('Calories describe 100 g of the final food. Recorded ingredient input weight is not final cooked yield or a serving count. Seller prices and stock are explicitly separate from the USDA reference.')
tabs=st.tabs(['Customer recommendations','Seller inventory & offers','Price catalog','Data & nutrition','Create a component meal'])

# Run seller controls first so publish/pause changes reach customer checkout on the same rerun.
with tabs[1]:
    st.header('Seller inventory and promotions')
    assessment_date=st.date_input('Inventory assessment date',value=DEFAULT_DATE,key='usda_assessment')
    st.caption('Fixed demo assessment date; expiry is exclusive. Source prices are historical; dates and stock below are seller-entered or explicitly simulated.')
    inventory_path=WORK/'seller_inventory.csv';inventory=load_inventory(inventory_path)
    with st.expander('Load a clearly labeled demonstration inventory'):
        demo_code=st.selectbox('Inventory example formulation',example_codes,index=default_example,format_func=lambda c:formulation_lookup[c]['name'])
        st.caption('Creates 50 simulated 100 g packs per component, with cost at 60% of its current catalog rate. Stock, cost, age, sales and expiry are invented demo inputs—not USDA observations. Existing batch IDs are preserved.')
        if st.button('Load simulated example batches'):
            demo=simulated_batches(formulation_lookup[demo_code],catalog,assessment_date)
            demo=demo[~demo.batch_id.isin(inventory.batch_id)]
            save_frame(inventory_path,pd.concat([inventory,demo],ignore_index=True))
            st.rerun()
    with st.expander('Create a batch from the USD catalog'):
        batch_food=st.selectbox('Batch food',list(lookup),format_func=lambda c:name_for(c),key='usda_batch_food')
        st.write(f"Selling price: **${lookup[batch_food]['price_per_100g_usd']*pack_sizes.get(batch_food,100)/100:.4f} / {pack_sizes.get(batch_food,100):g} g pack** · {lookup[batch_food]['price_basis']}")
        params=classification_parameters(classified).get(str(batch_food))
        st.caption(f'Formulation frequency: {params[0]:.1%} · {params[1]} · multiplier ×{params[2]:.1f}' if params else 'Not used in the current formulation/meal corpus; neutral frequency multiplier ×1.0.')
        with st.form('usda_create_batch'):
            batch_id=st.text_input('New batch ID')
            stock=st.number_input('Stock (configured packs)',min_value=1,value=50)
            reserve=st.number_input('Required supply (configured packs)',min_value=0,value=10)
            cost=st.number_input('Seller acquisition cost per configured pack (USD)',min_value=0.0,value=None,step=.001,format='%.4f')
            received=st.date_input('Batch received date',value=assessment_date)
            expiry=st.date_input('Batch expiry date',value=assessment_date+timedelta(days=7))
            sales=st.number_input('Average daily sales (configured packs)',min_value=0.0,value=2.0)
            holding=st.number_input('Target holding days',min_value=1,value=7)
            window=st.number_input('Markdown window days',min_value=1,value=7)
            if st.form_submit_button('Create batch and calculate discounts'):
                try:
                    if cost is None:raise ValueError('Enter the seller acquisition cost; USDA prices do not supply procurement costs.')
                    batch_catalog=pd.DataFrame({'ingredient_name':catalog.food_code.astype(str),'price_per_100g':catalog.price_per_100g_usd})
                    record=create_batch(batch_catalog,inventory,str(batch_food),batch_id,stock,reserve,cost,received,expiry,sales,holding,window,assessment_date,pack_size_g=pack_sizes.get(batch_food,100))
                    record.update(food_code=batch_food,inventory_origin='Seller-entered')
                except ValueError as exc:st.error(str(exc))
                else:
                    save_frame(inventory_path,pd.concat([inventory,pd.DataFrame([record])],ignore_index=True));st.rerun()
    with st.expander('Upload inventory CSV'):
        template='food_code,batch_id,stock_qty,required_qty,unit_cost,received_date,expiry_date,pack_size_g,avg_daily_sales,target_holding_days,markdown_window_days\n'
        st.download_button('Download inventory template',template,file_name='usda_inventory_template.csv',mime='text/csv')
        upload=st.file_uploader('Upload USD inventory',type=['csv'],key='usda_inventory_upload')
        st.caption('Selling prices are taken from the USD catalog. Required fields are food_code, batch_id, stock_qty, required_qty, unit_cost, received_date and expiry_date. Optional pack_size_g defaults to 100 g. Stock, reserve, daily sales and acquisition cost are measured per recorded pack. Imports add batches; duplicate IDs are rejected.')
        if upload is not None:
            try:incoming=inventory_upload(pd.read_csv(io.BytesIO(upload.getvalue())),catalog)
            except (ValueError,pd.errors.ParserError,pd.errors.EmptyDataError,UnicodeDecodeError) as exc:st.error(str(exc))
            else:
                st.dataframe(incoming,hide_index=True,width='stretch')
                if st.button('Import inventory batches'):
                    if incoming.batch_id.isin(inventory.batch_id).any():st.error('An imported batch ID already exists. Keep IDs unique.')
                    else:
                        save_frame(inventory_path,pd.concat([inventory,incoming],ignore_index=True));st.rerun()
    if not inventory.empty:
        with st.expander('Update existing batch quantities, cost or dates'):
            st.caption('Identity, stock unit, origin and saved selling price stay fixed. Stock/cost/date changes recalculate eligibility and can invalidate published offers. Saved batch selling prices are reference snapshots; current catalog prices determine new drafts and checkout.')
            editable=inventory.copy()
            editable['Food']=editable.food_code.map(lambda code:name_for(code))
            epoch=st.session_state.get('usda_editor_epoch',0)
            edited=st.data_editor(editable,num_rows='fixed',hide_index=True,width='stretch',
                disabled=['ingredient_name','food_code','batch_id','unit_price','stock_unit','inventory_origin','Food'],key=f'usda_inventory_editor_{epoch}')
            if st.button('Save inventory updates'):
                try:updated=validate_inventory_edits(edited,inventory,catalog)
                except ValueError as exc:st.error(str(exc))
                else:
                    save_frame(inventory_path,updated);st.session_state['usda_editor_epoch']=epoch+1;clear_receipt();st.rerun()
    cap=st.slider('Maximum discount (%)',0,40,30,key='usda_discount_cap')
    floor=st.slider('Minimum seller margin (%)',0,40,5,key='usda_margin_floor')
    size=st.select_slider('Items per combo',options=[2,3,4],value=2,key='usda_combo_size')
    scoring_label=st.selectbox('Inventory scoring algorithm',['Rule-based baseline','ML: learned unsold-stock risk'],index=1,key='usda_scoring_algorithm')
    scoring_mode='ml' if scoring_label.startswith('ML:') else 'rules'
    if scoring_mode=='ml':
        from ml_inventory import load_model
        model_info=load_model()
        st.warning('Experimental ML score trained on simulated sales outcomes, not real retailer history. Discount amounts still follow the seller cap and margin constraints.')
        with st.expander('ML model evaluation and learned coefficients'):
            st.write(model_info['algorithm']);st.write(model_info['target']);st.write(model_info['split'])
            st.json(model_info['evaluation'])
            st.dataframe(pd.DataFrame({'Feature':['intercept']+model_info['features'],'Standardized coefficient':model_info['coefficients']}),hide_index=True)
            st.caption('Coefficients were fitted to unsold-stock outcomes; they are not feature importance percentages or causal effects. Metrics measure performance on synthetic held-out products only.')
    offer_inventory=inventory.copy()
    if not offer_inventory.empty:
        compatible=offer_inventory.apply(lambda row:batch_pack_grams(row.stock_unit)==pack_sizes.get(int(row.food_code),100),axis=1)
        if not compatible.all():st.caption(f'{int((~compatible).sum())} batches excluded from offers because their pack sizes differ from the current catalog.')
        offer_inventory=offer_inventory[compatible]
    drafts,scored,omitted=draft_offers(offer_inventory,classified,catalog,assessment_date,max_discount=cap,minimum_margin=floor,min_items=size,max_items=size,scoring_mode=scoring_mode)
    if omitted:st.info(f'{omitted} eligible foods are outside this run’s 12-food candidate limit. Candidates use earliest expiry per food, then highest urgency. This bounds combination generation.')
    drafts=[o for o in drafts if all(pack_sizes.get(int(code),100)==o.get('quantities_g',{}).get(code,100) for code in o['items'])]
    if not scored.empty:
        display=scored.copy();display['Food']=display.ingredient_name.map(lambda c:name_for(c))
        st.dataframe(display,hide_index=True,width='stretch')
        excluded=display[~display.eligible]
        st.metric('Excluded inventory batches',len(excluded))
        if not excluded.empty:st.dataframe(excluded[['Food','batch_id','exclusion_reason']],hide_index=True,width='stretch')
    else:st.info('Create seller batches, upload inventory, or explicitly load the simulated example to calculate discounts.')
    if drafts:
        st.subheader('Draft offer decisions')
        decisions=pd.DataFrame([{'Combo':offer_title(o),'Quantities':o['quantity_description'],'Original (USD)':o['original_price'],'Offer (USD)':o['offer_price'],'Savings (USD)':o['savings'],'Effective discount (%)':round(o['effective_discount_pct'],2),'Cost (USD)':o['cost'],'Profit (USD)':o['profit'],'Margin (%)':round(o['margin_pct'],2),'Margin cap applied':o['margin_limited'],'Basis':o['inventory_origin'],'Reason':o['breakdown']} for o in drafts])
        st.dataframe(decisions,hide_index=True,width='stretch')
        st.download_button('Download draft offer decisions',decisions.to_csv(index=False).encode(),file_name='usda_offer_decisions.csv',mime='text/csv')
        st.caption('Each row is an alternative offer; shared stock means totals are not additive. One recorded pack per component, rounded to cents while retaining the margin floor. Frequency is recipe coverage, not sales demand.')
    publication_path=WORK/'published_offers.json'
    published=load_promotions(publication_path)
    st.subheader('Publish or pause customer offers')
    labels={promotion_id(o):f"{offer_title(o)} — ${o['offer_price']:.2f}" for o in drafts}
    all_drafts=st.checkbox('Select all draft offers for publishing',key='usda_publish_all')
    selected_drafts=st.multiselect('Draft offers to publish',list(labels),format_func=lambda key:labels[key],disabled=all_drafts,key='usda_publish_ids')
    if all_drafts:selected_drafts=list(labels)
    until=st.date_input('Promotion end date (exclusive)',value=assessment_date+timedelta(days=7),key='usda_promotion_end')
    if st.button('Publish selected offers',disabled=not selected_drafts):
        try:new=publish_snapshot([o for o in drafts if promotion_id(o) in selected_drafts],inventory,until,assessment_date)
        except ValueError as exc:st.error(str(exc))
        else:
            previous=list(published);ids={o['promotion_id'] for o in new}
            published=[o for o in published if o['promotion_id'] not in ids]+new
            save_promotions(publication_path,published);record_promotion_changes(publication_path,previous,published,'Published',assessment_date,currency='USD')
            st.success(f'Published {len(new)} offers. End dates are capped at the earliest batch expiry.')
    if published:
        to_pause=st.multiselect('Published offers to pause',[o['promotion_id'] for o in published if not o.get('paused')],format_func=lambda key:next(offer_title(o) for o in published if o['promotion_id']==key),key='usda_pause_ids')
        if st.button('Pause selected offers',disabled=not to_pause):
            previous=[dict(o) for o in published]
            for offer in published:
                if offer['promotion_id'] in to_pause:offer['paused']=True
            save_promotions(publication_path,published);record_promotion_changes(publication_path,previous,published,'Paused',assessment_date,currency='USD')
            st.success('Selected offers paused.')
    active=active_promotions(published,drafts,assessment_date)
    st.metric('Active published offers',len(active))
    if published:
        active_ids={o['promotion_id'] for o in active}
        st.dataframe(pd.DataFrame([{'Combo':offer_title(o),'Price (USD)':o['offer_price'],'Valid before':o['valid_until'],'Status':'Paused' if o.get('paused') else 'Active' if o['promotion_id'] in active_ids else 'Expired or needs republishing'} for o in published]),hide_index=True,width='stretch')
    st.caption('Customer offers and checkout are revalidated against current draft eligibility, stock, date, prices and margin settings. Changed or invalid offers require republishing.')
    with st.expander('Publication history'):
        history=promotion_history(publication_path)
        if history:
            frame=pd.DataFrame(history[::-1]);st.dataframe(frame.head(200),hide_index=True,width='stretch')
            st.download_button('Download publication history',frame.to_csv(index=False).encode(),file_name='usda_publication_history.csv',mime='text/csv')
        else:st.caption('No publication activity yet.')
    with st.expander('Add seller-entered preparation context'):
        st.caption('USDA does not provide cooking time or servings for this trial. These values are seller-entered, not USDA observations. Declared servings scale ingredient weights and costs to one serving; preparation time guides schedule suggestions.')
        menu_code=st.selectbox('Menu formulation',example_codes,index=default_example,format_func=lambda c:formulation_lookup[c]['name'])
        with st.form('usda_menu_context'):
            minutes=st.number_input('Declared preparation time (minutes)',min_value=0.1,value=menu.get(str(menu_code),{}).get('minutes'))
            servings=st.number_input('Declared servings for recorded batch',min_value=1,value=menu.get(str(menu_code),{}).get('servings'))
            if st.form_submit_button('Save preparation context'):
                menu[str(menu_code)]={'minutes':minutes,'servings':servings,'origin':'Seller-entered menu context'}
                save_promotions(WORK/'menu_context.json',menu);st.rerun()

with tabs[0]:
    st.header('Customer recommendations')
    if st.session_state.get('usda_success'):st.success(st.session_state.pop('usda_success'))
    context=st.selectbox('Optional schedule context',['No schedule preference','Busy / short break','After workout','Late study/work','Family meal'],key='usda_schedule')
    rules={'Busy / short break':'seller-declared preparation time ≤30 minutes','Late study/work':'seller-declared preparation time ≤20 minutes','Family meal':'seller-declared servings ≥2','After workout':'protein ≥10 g per 100 g, from USDA or a labeled component-weighted estimate (not nutritional advice)'}
    if context in rules:st.caption('Schedule rule: '+rules[context]+'. Missing preparation metadata is never inferred.')
    context_matches=offer_schedule_matches(active,formulations,context,menu)
    if not inventory.empty and inventory.inventory_origin.astype(str).str.startswith('SIMULATED').any():
        st.caption('This workspace includes explicitly simulated seller stock/cost/expiry scenarios; these are not observed USDA or retailer inventory.')
    if context in rules and active and not context_matches:
        st.info('No published offer currently satisfies this schedule rule. Other active offers remain available.')
    with st.expander('Browse published combo offers',expanded=bool(active)):
        if active:
            search=st.text_input('Search offers by component',key='usda_offer_query')
            order=st.selectbox('Order offers by',['Highest savings','Lowest bundle price','Ending soon'],key='usda_offer_order')
            # Shared search works on public food names, while publication/checkout stay code-based.
            searchable=[dict(o,items=[name_for(c) for c in o['items']],_original=o) for o in active]
            # Sort using the shared function, then restore exact code-based offers.
            browsed=browse_promotions(searchable,search,order);browsed=[o['_original'] for o in browsed]
            if context in rules and st.checkbox('Show schedule-matching offers first',value=True,key='usda_context_first'):
                browsed.sort(key=lambda o:promotion_id(o) not in context_matches)
            st.caption(f'{len(browsed)} matching active offers. Quantities: one listed pack of each included product.')
            page=st.selectbox('Offer page',list(range(1,max(1,(len(browsed)+7)//8)+1)))
            occupied={code for saved in st.session_state.get('usda_chosen_combos',[]) for code in saved['items']}
            for offer in browsed[(page-1)*8:page*8]:
                st.write(f"**{offer_title(offer)}** — ${offer['offer_price']:.2f} · Save ${offer['savings']:.2f} ({offer.get('effective_discount_pct',offer['discount_pct']):.1f}% after cent rounding)")
                st.caption(offer['quantity_description']+' · Valid before '+offer['valid_until'])
                if promotion_id(offer) in context_matches:st.caption('Fits your schedule via: '+', '.join(context_matches[promotion_id(offer)][:3]))
                overlap=bool(occupied.intersection(offer['items']))
                st.button('Add this published combo',key=f"usda_browse_{offer['promotion_id']}",on_click=add_combo,args=(offer,),disabled=overlap)
                if overlap:st.caption('A selected combo already covers a component in this offer.')
        else:st.info('No active published offers. The seller can create inventory and publish draft promotions.')
    example=st.selectbox('Example formulation',example_codes,index=default_example,format_func=lambda code:formulation_lookup[code]['name'])
    st.button('Load example ingredients',on_click=choose_example,args=(example,))
    selected=st.multiselect('Cart items',list(sorted(lookup,key=lambda c:name_for(c).casefold())),key='usda_selected',format_func=lambda c:f"{name_for(c)} · ${lookup[c]['price_per_100g_usd']:.3f}/100 g")
    cart_selected=selected
    selected=recipe_cart_codes(cart_selected,categories)
    if cart_selected:
        st.dataframe(pd.DataFrame([{'Item':name_for(code),'Cart category':categories[code]} for code in cart_selected]),hide_index=True,width='stretch')
    st.caption('Only recipe ingredients influence matching and additional-item counts. Ready-made food, snacks and utility items remain in checkout. Automatic categories can be corrected in the catalog.')
    preference=st.radio('Tie-break preference',['Fewest additional items','Budget-friendly (per 100 g input)','Lowest ingredient batch cost','Lowest calories per 100 g'],horizontal=True)
    query=st.text_input('Search formulations')
    eligible_formulations=[f for f in formulations if all(categories[int(i['food_code'])]=='Recipe ingredient' for i in f['ingredients'])]
    ranked=rank_formulations(eligible_formulations,selected,preference)
    if query.strip():ranked=[f for f in ranked if query.strip().casefold() in f['name'].casefold()]
    st.caption('Order: most selected ingredients used, then fewest additional items, then your preference. Schedule highlights do not override these counts.')
    st.write(f'**{len(ranked)} matching formulations**')
    if ranked:
        page=st.selectbox('Results page',list(range(1,(len(ranked)+9)//10+1)))
        for record in ranked[(page-1)*10:page*10]:
            with st.container(border=True):
                st.subheader(record['name'])
                if schedule_fit(record,context,menu.get(str(record['food_code']),{})):st.caption('Fits your schedule: '+rules[context])
                if selected:
                    used=[i for i in record['ingredients'] if i['food_code'] in selected]
                    st.write(f"Uses **{record['matched_count']} of your {len(selected)} selected items** · Additional required: **{record['additional_count']}**")
                    labels=[]
                    for item in used:
                        amount=item['batch_cost_usd']
                        labels.append(f"{item['name']} ({item['grams']:.1f} g · ${amount:.2f})")
                    st.caption('Selected ingredients needed for 1 serving: '+', '.join(labels)+'. Costs use recipe quantities for one serving before combo savings.')
                a,b=st.columns(2)
                a.metric('Ingredient cost for 1 serving (USD)',f"${record['ingredient_batch_cost_usd']:.2f}")
                kcal=record['kcal_per_100g'];b.metric('Calories / 100 g',f'{kcal:g} kcal' if kcal is not None else 'Unavailable')
                st.caption(record['serving_basis'])
                st.caption(record.get('calorie_basis','USDA final-food calories per 100 edible grams.'))
                st.caption(f"Ingredient cost normalized to 100 g input: ${record['ingredient_batch_cost_usd']/record['ingredient_batch_grams']*100:.3f}. This is not a finished serving price.")
                metadata=menu.get(str(record['food_code']),{})
                if metadata.get('minutes'):st.caption(f"Seller-declared preparation: {metadata['minutes']:g} minutes.")
                missing=[i for i in record['ingredients'] if i['food_code'] not in selected]
                if not missing:st.success('You have picked all the items required.')
                else:
                    st.write('**Additional ingredients:** '+', '.join(i['name'] for i in missing))
                    st.button('Add missing items to cart',key=f"usda_missing_{record['food_code']}",on_click=add_missing,args=(record['food_code'],active,inventory))
                    st.caption('Adds missing recipe quantities and applies eligible pack offers. Each combo component requires its listed pack weight. The bill combines combo and extra quantities into one row per item.')
                    missing_codes={str(i['food_code']) for i in missing}
                    matching=relevant_recipe_offers([str(i['food_code']) for i in record['ingredients']],missing_codes,active)
                    if matching:
                        st.success('Discounted combinations are available for your additional items')
                        for offer in matching[:3]:
                            st.write(f"{offer_title(offer)} — ${offer['offer_price']:.2f} · Save ${offer['savings']:.2f}")
                            st.caption(offer['quantity_description']+' · Valid before '+offer['valid_until'])
                            occupied={code for saved in st.session_state.get('usda_chosen_combos',[]) for code in saved['items']}
                            st.button('Add discounted combo to cart',key=f"usda_recipe_combo_{record['food_code']}_{promotion_id(offer)}",on_click=add_combo,args=(offer,),disabled=bool(occupied.intersection(offer['items'])))
                    else:
                        st.caption('No active published combo covers these additional requirements. Seller stock, publication and expiry determine availability.')
                with st.expander('Ingredient quantities and price basis'):
                    st.dataframe(pd.DataFrame([{'Food code':i['food_code'],'Component':i['name'],'Grams for 1 serving':round(i['grams'],2),'Catalog USD / 100 g':i['price_per_100g_usd'],'Cost for 1 serving (USD)':round(i['batch_cost_usd'],4)} for i in record['ingredients']]),hide_index=True,width='stretch')
                    st.caption(f"Input weight: {record['ingredient_batch_grams']:,.1f} g—not a final cooked yield or serving count.")
                    if record.get('fdc_id') is not None:
                        st.link_button('USDA nutrition source',f"https://fdc.nal.usda.gov/food-details/{record['fdc_id']}/nutrients")
    else:st.info('No formulation matches these selections and search terms.')
    st.subheader('Cart and simulated checkout')
    st.button('Clear cart',key='usda_clear_cart',on_click=clear_cart,help='Clears cart quantities, combos and invoice. Seller inventory, prices and publications stay saved.')
    if st.session_state.get('usda_notice'):st.warning(st.session_state.pop('usda_notice'))
    chosen=st.session_state.get('usda_chosen_combos',[])
    for index,offer in enumerate(chosen):
        st.write(f"Applied combo: **{offer_title(offer)} — ${offer['offer_price']:.2f}**")
        st.button('Remove combo',key=f'usda_remove_{index}',on_click=remove_combo,args=(index,))
    if cart_selected:
        quantities={}
        for code in cart_selected:
            key=f'usda_grams_{code}';st.session_state.setdefault(key,100.0)
            quantities[code]=st.number_input(f'{name_for(code)} quantity (g)',min_value=.1,step=10.0,key=key)
        plan=purchase_plan(quantities,pack_sizes)
        st.dataframe(pd.DataFrame([{'Item':name_for(r['food_code']),'Needed (g)':r['required_g'],'Pack size (g)':r['pack_size_g'],'Packs to buy':r['packs'],'Purchase weight (g)':r['purchased_g'],'Left after use (g)':r['leftover_g'],'Price basis':lookup[r['food_code']]['price_basis']} for r in plan]),hide_index=True,width='stretch')
        st.caption('Purchases round up to whole packs. Unconfigured products use the 100 g demo pack assumption. Pack prices use the current catalog rate: seller-entered prices where available, otherwise historical USDA estimates. Leftovers assume the entered required quantity is used.')
        try:lines=customer_lines(quantities,chosen,active,inventory,catalog,pack_sizes=pack_sizes,assessment_date=assessment_date)
        except ValueError as exc:
            clear_receipt();st.error(str(exc))
        else:
            frame=pd.DataFrame(lines);st.dataframe(frame,hide_index=True,width='stretch')
            st.caption('Stock is checked for tracked products against the assessment date; catalog-only products have unverified availability. Each product appears once. Combo and extra quantities are combined; combo savings are allocated across the eligible items for display. Pack requirements and the total discount are unchanged.')
            regular=round(sum(line['Regular (USD)'] for line in lines),2);payable=round(sum(line['Payable (USD)'] for line in lines),2)
            a,b,c=st.columns(3);a.metric('Regular cart total (USD)',f'${regular:.2f}');b.metric('Applied combo savings (USD)',f'${regular-payable:.2f}');c.metric('Selected ingredient total (USD)',f'${payable:.2f}')
            purchased={r['food_code']:r['purchased_g'] for r in plan}
            availability=[(f,recipe_availability(f,purchased)) for f in eligible_formulations]
            ready=[f['name'] for f,status in availability if status['ready']]
            if ready:st.success('With these purchased quantities, you can assemble one serving of: '+', '.join(ready)+'.')
            short_rows=[]
            for f,status in availability:
                if not status['ready'] and {int(i['food_code']) for i in f['ingredients']}<=set(selected):
                    for shortage in status['shortages']:
                        short_rows.append({'Recipe':f['name'],'Ingredient':name_for(shortage['food_code']),
                                           'Required (g)':round(shortage['required_g'],2),
                                           'Purchased (g)':round(shortage['available_g'],2),
                                           'Shortfall (g)':round(shortage['shortfall_g'],2)})
            if short_rows:
                with st.expander('Ingredients selected, but more quantity is needed'):
                    st.dataframe(pd.DataFrame(short_rows),hide_index=True,width='stretch')
            st.caption('Each recipe is checked independently against full purchased packs for one serving. These alternatives do not mean all recipes can be made together. Serving weights may be estimates. No payment, stock reservation or deduction occurs.')
            fingerprint=hashlib.sha256(json.dumps(lines,sort_keys=True).encode()+str(assessment_date).encode()).hexdigest()
            if st.session_state.get('usda_receipt_fingerprint')!=fingerprint:clear_receipt()
            if st.button('Confirm simulated checkout'):
                try:confirmed=customer_lines(quantities,chosen,active,inventory,catalog,pack_sizes=pack_sizes,assessment_date=assessment_date)
                except ValueError as exc:st.error(str(exc))
                else:
                    st.session_state['usda_receipt']=render_invoice(confirmed,assessment_date,currency='USD',price_note=('Reference estimates adjusted using US all-items CPI through '+SNAPSHOT['target_period']+'; verified '+SNAPSHOT['verified_on']+'. ' if inflation_enabled else 'Uses historical USDA 2017–2018 reference estimates. ')+'Seller-entered prices are used where supplied. Inflation estimates are not current retail quotes. Batches and discounts may be simulated.').encode('utf-8')
                    st.session_state['usda_receipt_fingerprint']=fingerprint
            if st.session_state.get('usda_receipt'):
                st.success('Your simulated USD invoice is ready.')
                html=st.session_state['usda_receipt'].decode()
                if hasattr(st,'iframe'):st.iframe(html,height=650,alt='Simulated USD invoice')
                else:components.html(html,height=650,scrolling=True)
                st.download_button('Download invoice (HTML)',st.session_state['usda_receipt'],file_name='smart_cart_usd_invoice.html',mime='text/html')
                st.caption('Open the downloaded invoice in a browser and use Print / Save as PDF.')
    else:st.info('Select components, load an example, or add a published combo to preview checkout.')

with tabs[2]:
    st.header('USD price catalog')
    st.caption('USDA reference prices and calories are read-only. Seller overrides are separate USD selling prices, not new USDA observations. Current catalog prices determine new drafts and checkout; saved batch price snapshots remain available for reference.')
    term=st.text_input('Find a food in the full catalog')
    viewed=catalog[catalog.name.str.contains(term,case=False,regex=False)] if term else catalog
    st.dataframe(viewed.head(250),hide_index=True,width='stretch')
    st.download_button('Download matched food data (CSV)',viewed.to_csv(index=False).encode(),file_name='usda_matched_food_data.csv',mime='text/csv')
    with st.expander('Upload seller price overrides'):
        st.download_button('Download USD price template','food_code,selling_price_per_100g_usd\n',file_name='usda_seller_price_template.csv',mime='text/csv')
        upload=st.file_uploader('Upload seller prices (USD)',type=['csv'],key='usda_price_upload')
        if upload is not None:
            try:incoming=validate_price_upload(pd.read_csv(io.BytesIO(upload.getvalue())),reference)
            except (ValueError,pd.errors.ParserError,pd.errors.EmptyDataError,UnicodeDecodeError) as exc:st.error(str(exc))
            else:
                st.dataframe(incoming,hide_index=True,width='stretch')
                if st.button('Apply seller price overrides'):
                    combined=pd.concat([overrides,incoming],ignore_index=True).drop_duplicates('food_code',keep='last')
                    save_frame(WORK/'seller_prices.csv',combined);clear_receipt();st.rerun()
    with st.expander('Retail pack sizes'):
        st.caption('Seller-entered pack weights, separate from USDA data. Default: simulated 100 g packs. Inventory batches and offers use their recorded pack weights. Changing a catalog pack size hides incompatible offers; create matching batches and publish new offers.')
        pack_code=st.selectbox('Product pack size',list(lookup),format_func=name_for,key='usda_pack_code')
        with st.form('usda_pack_form'):
            size_g=st.number_input('Pack weight (g)',min_value=.1,value=pack_sizes.get(pack_code,100.0))
            pack_price=st.number_input('Optional selling price for this whole pack (USD)',min_value=.01,value=None,step=.01)
            st.caption('Entering a pack price updates the seller catalog rate as pack price ÷ pack grams × 100. Leaving it blank keeps the current rate. Existing quotes are revalidated.')
            if st.form_submit_button('Save pack size'):
                if pack_price is not None:
                    rate=pack_price_rate(size_g,pack_price)
                    incoming=validate_price_upload(pd.DataFrame([{'food_code':pack_code,'selling_price_per_100g_usd':rate}]),reference)
                    save_frame(WORK/'seller_prices.csv',pd.concat([overrides,incoming],ignore_index=True).drop_duplicates('food_code',keep='last'))
                updated=pd.DataFrame([{'food_code':pack_code,'pack_size_g':size_g}])
                save_frame(WORK/'pack_sizes.csv',pd.concat([pack_frame,updated],ignore_index=True).drop_duplicates('food_code',keep='last'))
                clear_receipt();st.rerun()
    with st.expander('Product cart classification'):
        st.caption('Seller classifications override name-based suggestions and are saved separately from USDA source data. Utility products are not supplied by this food-only dataset.')
        category_code=st.selectbox('Product to classify',list(lookup),format_func=name_for,key='usda_category_code')
        with st.form('usda_category_form'):
            category=st.selectbox('Cart category',CATEGORIES,index=CATEGORIES.index(categories[category_code]))
            if st.form_submit_button('Save product classification'):
                updated=pd.DataFrame([{'food_code':category_code,'category':category}])
                save_frame(WORK/'product_categories.csv',pd.concat([category_overrides,updated],ignore_index=True).drop_duplicates('food_code',keep='last'))
                clear_receipt();st.rerun()
    with st.expander('Enter one seller price'):
        code=st.selectbox('Food to reprice',list(lookup),format_func=name_for,key='usda_reprice_food')
        with st.form('usda_price_form'):
            price=st.number_input('Seller selling price per 100 g (USD)',min_value=.0001,value=None,format='%.4f')
            if st.form_submit_button('Save seller price'):
                try:incoming=validate_price_upload(pd.DataFrame([dict(food_code=code,selling_price_per_100g_usd=price)]),reference)
                except ValueError as exc:st.error(str(exc))
                else:
                    save_frame(WORK/'seller_prices.csv',pd.concat([overrides,incoming],ignore_index=True).drop_duplicates('food_code',keep='last'));clear_receipt();st.rerun()

with tabs[3]:
    st.header('Data compatibility and nutrition')
    st.write(f"{manifest['matched_price_and_calorie_records']:,} prices join exactly by USDA food code. {len(source_formulations)} USDA multi-component formulations have known gram weights and prices for every component. SR/NDB ingredient codes without public prices remain excluded.")
    st.caption('USDA components may already be prepared foods. Some survey formulations are composites, not literal cooking recipes. Price construction methods are retained; cooking times, retailer procurement costs, stock and expiry are not supplied by this data.')
    st.link_button('USDA Purchase-to-Plate documentation','https://www.ers.usda.gov/data-products/purchase-to-plate')
    st.link_button('USDA FoodData Central downloads','https://fdc.nal.usda.gov/download-datasets/')
    st.json(manifest)


with tabs[4]:
    st.header('Create your own priced component meal')
    st.caption('Combine known USDA components with your own gram quantities. This does not become an official USDA formulation. Cost uses current USD catalog prices; calories are a component-weighted estimate, not a measured cooked-food result.')
    custom_codes=st.multiselect('Components for your meal',list(lookup),format_func=name_for,key='usda_custom_codes')
    with st.form('usda_custom_meal'):
        meal_name=st.text_input('Meal name')
        weights={code:st.number_input(f'{name_for(code)} meal quantity (g)',min_value=.1,value=100.0,key=f'usda_custom_g_{code}') for code in custom_codes}
        meal_minutes=st.number_input('Optional preparation time (minutes)',min_value=.1,value=None)
        meal_servings=st.number_input('Optional declared servings',min_value=1,value=None)
        if st.form_submit_button('Save component meal'):
            try:record=custom_formulation(meal_name,weights,catalog)
            except ValueError as exc:st.error(str(exc))
            else:
                save_promotions(WORK/'custom_formulations.json',custom_records+[record])
                menu[str(record['food_code'])]={'minutes':meal_minutes,'servings':meal_servings,'origin':'User-entered meal context'}
                save_promotions(WORK/'menu_context.json',menu)
                st.session_state['usda_success']='Your component meal is saved and available in customer recommendations.'
                st.rerun()
