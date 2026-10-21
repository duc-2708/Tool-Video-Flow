"""Shot keys use scene IDs and one-based ordinals within that plan only."""
def shot_lookup(plan):
    return {(scene.id, ordinal): shot
            for scene in plan.scenes for ordinal, shot in enumerate(scene.shots, 1)}
