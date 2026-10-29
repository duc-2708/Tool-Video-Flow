with open("pipeline/run_all.py", "r", encoding="utf-8") as f:
    c = f.read()

old_s = 'if getattr(settings, "script_v3_enabled", False):'
new_s = 'if getattr(settings, "script_v3_enabled", False) or getattr(settings, "motion_recipes_enabled", True):'
assert old_s in c, "old_s not found in run_all.py"
c = c.replace(old_s, new_s)

with open("pipeline/run_all.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Successfully updated pipeline/run_all.py!")
