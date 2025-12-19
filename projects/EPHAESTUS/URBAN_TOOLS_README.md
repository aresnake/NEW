# Nouveaux Outils Urbains Hephaestus

## ✅ Outils Implémentés (5 outils prioritaires)

### 1. `create_building_box` - Création de volume de bâtiment
Crée un volume de bâtiment paramétrique avec divisions d'étages.

**Paramètres:**
- `width`: Largeur du bâtiment (défaut: 10.0m)
- `depth`: Profondeur du bâtiment (défaut: 10.0m)
- `height`: Hauteur totale (défaut: 15.0m)
- `floors`: Nombre d'étages (défaut: 5)
- `name`: Nom de l'objet (défaut: "Building")

**Exemple:**
```python
result = create_building_box(width=12.0, depth=8.0, height=20.0, floors=6, name="Office")
```

### 2. `create_window_grid` - Grille de fenêtres paramétriques
Crée une grille de fenêtres sur un bâtiment existant.

**Paramètres:**
- `building_name`: Nom du bâtiment cible (requis)
- `floors`: Nombre d'étages (défaut: 5)
- `windows_per_floor`: Fenêtres par étage (défaut: 4)
- `window_width`: Largeur des fenêtres (défaut: 1.5m)
- `window_height`: Hauteur des fenêtres (défaut: 2.0m)
- `spacing`: Espacement entre fenêtres (défaut: 0.5m)
- `inset`: Distance d'incrustation (défaut: 0.1m)

**Exemple:**
```python
result = create_window_grid(
    building_name="Office",
    floors=6,
    windows_per_floor=5,
    window_width=1.8,
    window_height=2.2
)
```

### 3. `array_along_path` - Array le long d'un chemin
Duplique un objet le long d'une courbe.

**Paramètres:**
- `source_object`: Nom de l'objet à dupliquer (requis)
- `curve_name`: Nom de la courbe à suivre (requis)
- `count`: Nombre de duplicatas (défaut: 10)
- `align_to_curve`: Aligner à la direction de la courbe (défaut: True)
- `spacing_factor`: Facteur d'espacement (défaut: 1.0)

**Exemple:**
```python
result = array_along_path(
    source_object="Streetlamp",
    curve_name="Road_Curve",
    count=20,
    spacing_factor=1.2
)
```

### 4. `randomize_transform` - Variation aléatoire
Ajoute de la variation aléatoire aux transforms d'objets.

**Paramètres:**
- `object_names`: Liste des objets (None = sélection) (défaut: None)
- `location_range`: Plage position (X, Y, Z) (défaut: (0, 0, 0))
- `rotation_range`: Plage rotation (X, Y, Z) en radians (défaut: (0, 0, 0))
- `scale_range`: Plage échelle (X, Y, Z) multiplicateur (défaut: (0, 0, 0))
- `seed`: Graine aléatoire (défaut: 0)

**Exemple:**
```python
result = randomize_transform(
    object_names=["Tree.001", "Tree.002", "Tree.003"],
    location_range=(0.5, 0.5, 0.0),
    rotation_range=(0.0, 0.0, 0.3),
    scale_range=(0.1, 0.1, 0.15),
    seed=42
)
```

### 5. `create_stairs` - Escaliers paramétriques
Crée des escaliers paramétriques.

**Paramètres:**
- `steps`: Nombre de marches (défaut: 10)
- `step_width`: Largeur des marches (défaut: 2.0m)
- `step_depth`: Profondeur des marches (défaut: 0.3m)
- `step_height`: Hauteur des marches (défaut: 0.2m)
- `name`: Nom de la collection (défaut: "Stairs")
- `location`: Position de départ (X, Y, Z) (défaut: (0, 0, 0))

**Exemple:**
```python
result = create_stairs(
    steps=15,
    step_width=3.0,
    step_depth=0.35,
    step_height=0.18,
    name="MainStairs",
    location=(5, 0, 0)
)
```

## 📝 Installation et Test

### Étape 1 : Recharger l'addon Blender
**IMPORTANT:** Après avoir appliqué les modifications, vous DEVEZ recharger l'addon :

**Option A - Recharger l'addon :**
1. Edit → Preferences → Add-ons
2. Rechercher "Hephaestus MCP"
3. Décocher → Recocher

**Option B - Redémarrer Blender** (recommandé)

### Étape 2 : Tester les outils

**Test 1 - Créer un bâtiment :**
```python
from hephaestus.connection import ensure_connected
conn = ensure_connected()
result = conn.send_command('create_building_box', {
    'width': 12.0,
    'depth': 8.0,
    'height': 20.0,
    'floors': 6,
    'name': 'TestBuilding'
})
print(result)
```

**Test 2 - Ajouter des fenêtres :**
```python
result = conn.send_command('create_window_grid', {
    'building_name': 'TestBuilding',
    'floors': 6,
    'windows_per_floor': 5
})
print(result)
```

**Test 3 - Créer des escaliers :**
```python
result = conn.send_command('create_stairs', {
    'steps': 12,
    'name': 'EntranceStairs',
    'location': [15, 0, 0]
})
print(result)
```

## 🎯 Workflow Exemple : Scène Urbaine

```python
from hephaestus.tools import urban

# 1. Créer un bâtiment
building = urban.create_building_box(
    width=15.0, depth=12.0, height=25.0,
    floors=8, name="Building_A"
)

# 2. Ajouter des fenêtres
windows = urban.create_window_grid(
    building_name="Building_A",
    floors=8,
    windows_per_floor=6,
    window_width=1.6,
    window_height=2.0
)

# 3. Ajouter des escaliers d'entrée
stairs = urban.create_stairs(
    steps=8,
    step_width=4.0,
    location=(-10, 0, 0),
    name="Entrance"
)

# 4. Créer une courbe pour les lampadaires (dans Blender manuellement)
# Puis array les lampadaires
lamps = urban.array_along_path(
    source_object="Lamp_Base",
    curve_name="Street_Path",
    count=25
)

# 5. Ajouter de la variation aux lampadaires
variation = urban.randomize_transform(
    object_names=None,  # Utilisera les objets sélectionnés
    rotation_range=(0.0, 0.0, 0.1),
    scale_range=(0.05, 0.05, 0.08),
    seed=123
)
```

## 🚀 Prochains Outils Recommandés

Basé sur l'ordre de priorité pour assets urbains :

1. **create_intersection** - Carrefours routiers
2. **procedural_facade** - Façades procédurales complètes
3. **create_street_lamp** - Lampadaires paramétriques
4. **create_lod_variants** - Génération automatique de LODs
5. **distribute_on_grid** - Distribution sur grille avec variation
6. **create_roof** - Toits (plat, pente, mansardé)
7. **create_door** - Portes paramétriques
8. **create_railing** - Garde-corps
9. **random_building_generator** - Générateur de bâtiments aléatoires
10. **create_parking_lot** - Parkings avec places

## 📊 Statistiques

- **Outils ajoutés:** 5
- **Lignes de code (addon.py):** ~233 lignes
- **Lignes de code (urban.py):** ~145 lignes
- **Lignes de code (server.py):** ~130 lignes
- **Total:** ~508 lignes de nouveau code

## ⚠️ Notes Importantes

1. **Recharger l'addon** après chaque modification de `addon.py`
2. **Tester progressivement** - Ne pas tout tester en même temps
3. **Vérifier la scène** - Certains outils créent beaucoup d'objets
4. **Performance** - `create_window_grid` peut créer 20+ objets
5. **Collections** - `create_stairs` organise automatiquement en collection

## 🐛 Dépannage

**Erreur "Unknown command type":**
- L'addon n'a pas été rechargé dans Blender
- Redémarrez Blender

**Connexion refusée:**
- Vérifier que le serveur Hephaestus tourne dans Blender
- Panel Hephaestus (N) → "Start Hephaestus Server"

**Objets mal positionnés:**
- Vérifier les paramètres de location
- Les dimensions sont en unités Blender (mètres)
