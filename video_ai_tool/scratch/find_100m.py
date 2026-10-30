import json
p = json.load(open('output/auto-cong-nghe-efa8eac5/edit_plan.json', encoding='utf-8'))
sc1 = p['scenes'][0]
vp_data = sc1.get('visual_plan', {}).get('data', {})
for k, v in vp_data.items():
    if '100000000' in str(v):
        print(f"vp_data.{k} = {v}")
for idx, s in enumerate(sc1.get('shots', [])):
    sd = s.get('visual', {}).get('data', {})
    for k, v in sd.items():
        if '100000000' in str(v):
            print(f"shot {idx} data.{k} = {v}")
