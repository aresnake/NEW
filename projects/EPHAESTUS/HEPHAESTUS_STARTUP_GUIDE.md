# Hephaestus - Guide de Démarrage from Scratch

## 🔥 Hephaestus : Le Meilleur MCP Blender du Monde

> Nommé d'après le dieu grec de la forge et de la création, Hephaestus est conçu pour être THE reference MCP pour Blender + LLM workflows.

---

## 📋 Prérequis

- **Python 3.10+**
- **uv** (package manager) - `pip install uv` ou `brew install uv` (Mac)
- **Blender 3.0+**
- **Claude Desktop** ou **Cursor** avec support MCP
- **Git** (optionnel mais recommandé)

---

## 🚀 Démarrage Rapide : Commandes Claude Code

### Étape 1 : Créer le projet dans un dossier vide

```
Claude, je veux créer un nouveau MCP Blender appelé "Hephaestus".
Crée la structure de projet suivante dans le dossier actuel :

hephaestus/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── addon.py                 # Blender addon (bridge)
├── main.py                  # Entry point MCP
├── src/
│   └── hephaestus/
│       ├── __init__.py
│       ├── server.py        # MCP server principal
│       ├── connection.py    # Socket connection avec Blender
│       ├── tools/           # Tous les tools organisés
│       │   ├── __init__.py
│       │   ├── scene.py
│       │   ├── objects.py
│       │   ├── materials.py
│       │   ├── modifiers.py
│       │   ├── camera.py
│       │   ├── lighting.py
│       │   └── macros.py
│       ├── presets/         # JSON presets
│       │   ├── lighting/
│       │   ├── materials/
│       │   └── scenes/
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   └── __init__.py
└── docs/
    ├── API.md
    ├── TOOLS_LIST.md
    └── EXAMPLES.md

Utilise ces spécifications pour pyproject.toml :
- Nom du package : hephaestus
- Version : 0.1.0
- Dépendances : mcp, asyncio
- Python : >=3.10

Pour README.md, inclus :
- Description du projet
- Installation rapide
- Architecture (2 composants : addon + MCP server)
- Quick start exemple
```

---

## 📝 Prompts Détaillés par Étape

### Étape 2 : Setup du MCP Server de Base

```
Maintenant, implémente le MCP server de base dans src/hephaestus/server.py :

1. Utilise FastMCP comme framework
2. Crée une classe BlenderConnection dans connection.py qui :
   - Se connecte à Blender via socket (localhost:9876 par défaut)
   - Peut envoyer des commandes JSON
   - Peut recevoir des réponses
   - Gère les timeouts et reconnexions
3. Implémente ces premiers tools dans tools/scene.py :
   - get_scene_info() -> retourne objets, collections, materials
   - get_object_info(object_name) -> détails d'un objet
   - get_viewport_screenshot(max_size=800) -> screenshot PNG

Structure de communication JSON :
Envoi : {"type": "command_name", "params": {...}}
Réponse : {"status": "success/error", "result": {...}, "message": "..."}

Assure-toi que le server démarre avec : uvx hephaestus
```

---

### Étape 3 : Créer l'Addon Blender

```
Crée maintenant l'addon Blender dans addon.py :

L'addon doit :
1. Créer un serveur socket qui écoute sur localhost:9876
2. Avoir un panel UI dans la sidebar (touche N) avec :
   - Bouton "Start Hephaestus Server"
   - Bouton "Stop Server"
   - Indicateur de status (connecté/déconnecté)
   - Port configuration

3. Gérer ces commandes :
   - "get_scene_info" -> retourne liste des objets avec type, location, etc.
   - "get_object_info" -> détails d'un objet spécifique
   - "get_viewport_screenshot" -> capture viewport et sauvegarde PNG
   - "execute_code" -> exécute du Python dans Blender (pour flexibilité)

4. Utiliser threading pour ne pas bloquer Blender UI

bl_info :
- name: "Hephaestus MCP"
- author: "Hephaestus Team"
- version: (0, 1, 0)
- blender: (3, 0, 0)
- category: "Interface"
```

---

### Étape 4 : Implémenter les Tools Essentiels

```
Implémente maintenant les tools prioritaires identifiés lors de la modélisation urbaine.

Dans tools/objects.py, crée :

1. create_primitive(type, name, location, scale, rotation)
   - type: "cube", "sphere", "cylinder", "cone", "plane", "torus"
   - Smart defaults si params non fournis

2. delete_object(name)
   - Supprime l'objet et ses dépendances

3. transform_object(name, location=None, rotation=None, scale=None)
   - Met à jour transform d'un objet
   - Tous params optionnels

4. duplicate_object(name, new_name, location_offset=None)
   - Duplique un objet avec nouveau nom

5. parent_object(child_name, parent_name, keep_transform=True)
   - Parentage d'objets

6. array_objects(object_name, count, offset, axis="X")
   - Array simple le long d'un axe

Chaque tool doit :
- Avoir une docstring claire
- Valider les paramètres
- Retourner un dict {"success": bool, "message": str, "data": {...}}
- Gérer les erreurs proprement
```

---

### Étape 5 : Materials System

```
Dans tools/materials.py, implémente :

1. create_material(name, base_color, roughness=0.5, metallic=0.0)
   - Crée un material Principled BSDF
   - base_color: tuple (r, g, b) ou (r, g, b, a)

2. assign_material(object_name, material_name, slot=0)
   - Assigne material à un objet

3. create_material_preset(preset_name, custom_name=None)
   - Presets disponibles :
     - "concrete" -> gray, rough
     - "metal_dark" -> dark, metallic
     - "metal_chrome" -> mirror-like
     - "glass" -> transparent
     - "plastic" -> colored, semi-glossy
     - "wood" -> brown, textured
     - "emission" -> light-emitting

4. set_material_property(material_name, property, value)
   - Properties: base_color, roughness, metallic, emission_strength, etc.

Stocke les presets dans src/hephaestus/presets/materials/ en JSON.
```

---

### Étape 6 : Modifiers

```
Dans tools/modifiers.py :

1. add_modifier(object_name, modifier_type, name=None, **params)
   - Types supportés :
     - ARRAY : count, offset, offset_type
     - MIRROR : axis, use_x, use_y, use_z
     - SUBDIVISION : levels, render_levels
     - BOOLEAN : operation, object
     - SOLIDIFY : thickness
     - BEVEL : width, segments

2. modify_modifier(object_name, modifier_name, **params)
   - Change les paramètres d'un modifier existant

3. apply_modifier(object_name, modifier_name)
   - Applique le modifier

4. remove_modifier(object_name, modifier_name)

5. boolean_operation(object_a, object_b, operation="DIFFERENCE")
   - Helper pour boolean ops
   - Operations: DIFFERENCE, UNION, INTERSECT
```

---

### Étape 7 : Camera Tools

```
Dans tools/camera.py :

1. create_camera(name, location, rotation=None)
   - Crée une caméra

2. set_active_camera(camera_name)
   - Définit la caméra active

3. point_camera_at(camera_name, target)
   - target peut être un objet name ou (x, y, z)
   - Utilise Track To constraint

4. set_camera_orthographic(camera_name, scale=10)
   - Passe en vue orthographique

5. set_camera_preset(camera_name, preset)
   - Presets :
     - "isometric" -> (45°, 0°, 45°) orthographic
     - "top" -> vue du dessus
     - "front" -> vue de face
     - "product" -> 3/4 view optimale

6. create_camera_rig(type="turntable", target=None)
   - Crée un rig caméra animé
```

---

### Étape 8 : Lighting System

```
Dans tools/lighting.py :

1. create_light(type, name, location, energy=100, color=None)
   - Types: POINT, SUN, SPOT, AREA

2. set_light_property(light_name, property, value)
   - Properties: energy, color, size (pour AREA), angle (pour SPOT)

3. apply_lighting_preset(preset_name)
   - Presets critiques :
     - "three_point" : Key + Fill + Rim
     - "studio" : Soft studio setup
     - "sunset" : Warm outdoor
     - "dramatic" : High contrast
     - "soft" : Diffuse lighting

4. set_world_hdri(hdri_path, rotation=0, strength=1.0)
   - Pour HDRI environments

Stocke les lighting presets en JSON avec positions, énergies, couleurs.
```

---

### Étape 9 : Collections & Organization

```
Dans tools/scene.py, ajoute :

1. create_collection(name, parent=None, color=None)
   - Crée une collection
   - color pour l'UI Blender

2. move_to_collection(object_names, collection_name)
   - object_names peut être string ou list
   - Déplace objets vers collection

3. get_collection_tree()
   - Retourne hierarchie complète des collections

4. batch_select(pattern, object_type=None)
   - Sélectionne objets par pattern (regex)
   - object_type : MESH, LIGHT, CAMERA, etc.

5. batch_operation(object_names, operation, **params)
   - Applique une opération sur plusieurs objets
   - operation peut être n'importe quel tool
```

---

### Étape 10 : Macros High-Level (GAME CHANGER!)

```
Dans tools/macros.py, implémente des macros intelligentes :

1. create_product_showcase(object_name, style="minimal")
   - Styles : minimal, studio, dramatic
   - Auto-crée : caméra isométrique, lighting 3-point, floor plane
   - Configure render settings
   - Retourne setup complet

2. create_studio_setup(size="medium", style="soft")
   - Crée un studio complet : lights, backdrop, camera
   - size : small, medium, large
   - style : soft, dramatic, high_key

3. apply_architectural_lighting(time_of_day="midday")
   - time_of_day : sunrise, midday, sunset, night
   - Configure sun + ambient

4. quick_render_setup(quality="preview")
   - quality : preview, medium, high, production
   - Configure samples, resolution, denoising

5. organize_scene()
   - Auto-crée collections par type
   - Nomme objets proprement
   - Range la scène

Ces macros sont le SUPER POUVOIR du MCP - permettent des setups complexes en 1 commande !
```

---

### Étape 11 : Configuration & Testing

```
Crée la configuration pour Claude Desktop/Cursor :

1. Dans docs/, crée INSTALLATION.md avec :
   - Installation uv
   - Installation addon dans Blender
   - Configuration claude_desktop_config.json
   - Configuration Cursor MCP

2. Crée des tests dans tests/ :
   - test_connection.py : teste la connexion socket
   - test_objects.py : teste création/modification objets
   - test_materials.py : teste materials
   - test_macros.py : teste les macros

3. Ajoute des exemples dans docs/EXAMPLES.md :
   - "Create a product showcase for a watch"
   - "Build a simple urban scene with buildings and street lamps"
   - "Setup a studio for character rendering"
```

---

## 🎯 Gaps Identifiés (à implémenter)

Voici les 12 gaps identifiés lors de la session de modélisation urbaine :

| # | Gap | Tool à créer | Priorité |
|---|-----|--------------|----------|
| 1 | Snap/Align | `snap_to_grid()`, `align_objects()` | Medium |
| 2 | Delete object | `delete_object(name)` | **HIGH** |
| 3 | Create primitives | `create_primitive(type, ...)` | **HIGH** |
| 4 | Modifiers | `add_modifier()`, `modify_modifier()` | **HIGH** |
| 5 | Boolean ops | `boolean_operation()` | **HIGH** |
| 6 | Parenting | `parent_object()` | Medium |
| 7 | Camera setup | `set_camera_position()`, `point_camera_at()` | **HIGH** |
| 8 | Materials | `create_material()`, `assign_material()` | **HIGH** |
| 9 | Error handling | Better error messages | Medium |
| 10 | Duplication | `duplicate_object()`, `array_objects()` | **HIGH** |
| 11 | Collections | `create_collection()`, `move_to_collection()` | **HIGH** |
| 12 | Collection info | `get_object_collection()` | Low |

---

## 📦 Structure Finale du Projet

```
hephaestus/
├── README.md                           # Vue d'ensemble
├── LICENSE                             # MIT ou Apache 2.0
├── pyproject.toml                      # Config Python/uv
├── uv.lock                            # Lock dependencies
├── addon.py                           # Blender addon (20-30KB)
├── main.py                            # Entry point : uvx hephaestus
│
├── src/hephaestus/
│   ├── __init__.py
│   ├── server.py                      # MCP server FastMCP
│   ├── connection.py                  # Socket connection
│   │
│   ├── tools/                         # 50+ tools
│   │   ├── __init__.py
│   │   ├── scene.py                   # Scene & collections
│   │   ├── objects.py                 # Object manipulation
│   │   ├── materials.py               # Materials & shaders
│   │   ├── modifiers.py               # Modifiers
│   │   ├── camera.py                  # Camera tools
│   │   ├── lighting.py                # Lights & HDRI
│   │   ├── macros.py                  # High-level macros
│   │   ├── animation.py               # (Phase 2)
│   │   └── rendering.py               # (Phase 2)
│   │
│   ├── presets/                       # JSON presets
│   │   ├── lighting/
│   │   │   ├── three_point.json
│   │   │   ├── studio.json
│   │   │   └── dramatic.json
│   │   ├── materials/
│   │   │   ├── concrete.json
│   │   │   ├── metal.json
│   │   │   └── glass.json
│   │   └── cameras/
│   │       ├── product.json
│   │       └── isometric.json
│   │
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py                 # Helper functions
│       └── validators.py              # Param validation
│
├── tests/
│   ├── __init__.py
│   ├── test_connection.py
│   ├── test_objects.py
│   ├── test_materials.py
│   └── test_macros.py
│
└── docs/
    ├── INSTALLATION.md                # Guide installation
    ├── API.md                         # API reference complète
    ├── TOOLS_LIST.md                  # Liste de tous les tools
    ├── EXAMPLES.md                    # Exemples d'usage
    └── ARCHITECTURE.md                # Architecture détaillée
```

---

## 🔄 Workflow de Développement avec Claude Code

### Session 1 : Bootstrap
```
Prompt : "Crée la structure de base du projet Hephaestus avec les fichiers squelettes"
Résultat : Structure + pyproject.toml + README
```

### Session 2 : Core Connection
```
Prompt : "Implémente le MCP server de base et la connection socket"
Résultat : server.py + connection.py fonctionnels
```

### Session 3 : Addon Blender
```
Prompt : "Crée l'addon Blender avec UI et socket server"
Résultat : addon.py complet et testable
```

### Session 4-8 : Tools par catégorie
```
Prompts : "Implémente les tools de [objects/materials/modifiers/etc.]"
Résultat : Chaque fichier tools/ complété
```

### Session 9 : Macros
```
Prompt : "Implémente les macros high-level dans macros.py"
Résultat : Macros game-changing
```

### Session 10 : Testing & Polish
```
Prompt : "Crée les tests et la documentation"
Résultat : Projet prêt pour release
```

---

## 🚀 Usage Final

### Installation
```bash
# Installer le MCP
uv pip install hephaestus

# Dans Blender
# Edit > Preferences > Add-ons > Install > addon.py
# Activer "Hephaestus MCP"
# Sidebar (N) > Hephaestus > Start Server
```

### Configuration Claude Desktop
```json
{
  "mcpServers": {
    "hephaestus": {
      "command": "uvx",
      "args": ["hephaestus"]
    }
  }
}
```

### Exemples d'utilisation
```
User: "Create a product showcase for a luxury watch"

Claude: *Uses macro create_product_showcase()*
✓ Camera isométrique créée
✓ Lighting 3-point appliqué
✓ Floor plane ajouté
✓ Render settings configurés

User: "Add a concrete material to the building"

Claude: *Uses create_material_preset("concrete") + assign_material()*
✓ Material "Concrete" créé
✓ Assigné au building

User: "Duplicate this lamp 5 times along the street"

Claude: *Uses array_objects() ou duplicate_object() in loop*
✓ 5 lampadaires créés avec espacement
```

---

## 🎯 Différences vs MCP Existant

| Feature | MCP Actuel | Hephaestus |
|---------|-----------|------------|
| Nombre de tools | ~22 | **100+** |
| Niveau abstraction | Bas | **Haut + Mid + Bas** |
| Macros | ❌ | **✅ Game changer** |
| Presets | Limités | **Extensive library** |
| Organisation | Monolithic | **Modulaire par domaine** |
| Materials | Basic | **Preset system** |
| Modifiers | Via code | **Direct tools** |
| Collections | Via code | **First-class support** |
| Camera helpers | ❌ | **✅ Presets + pointing** |
| Lighting presets | ❌ | **✅ Studio-ready** |
| Documentation | Basic | **Complete + examples** |

---

## 🏆 Success Metrics

1. **Speed** : Créer une scène complexe en <10 tool calls
2. **Coverage** : 100+ tools couvrant 90% des use cases
3. **Quality** : Tous tools documentés + testés
4. **UX** : LLM peut utiliser sans friction
5. **Community** : Template sharing system

---

## 📚 Ressources

### Pour le développement
- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Blender Python API](https://docs.blender.org/api/current/)
- [Socket Programming Python](https://docs.python.org/3/library/socket.html)

### Inspiration
- Blender MCP actuel (référence)
- BlenderKit addon (pour asset management)
- Rigify addon (pour presets system)

---

## 🎨 Vision Long Terme

### Phase 1 (MVP) - 2 semaines
✅ Core tools (objects, materials, modifiers)
✅ Basic macros
✅ Lighting presets

### Phase 2 - 1 mois
✅ Animation tools
✅ Rendering presets
✅ Geometry Nodes basics

### Phase 3 - 2-3 mois
✅ Advanced Geometry Nodes
✅ Rigging helpers
✅ Physics simulation

### Phase 4+ - Long terme
✅ AI-powered suggestions
✅ Template marketplace
✅ Community presets
✅ Blender Cloud integration

---

## 💡 Tips pour Claude Code

1. **Commencer simple** : Bootstrap d'abord, features ensuite
2. **Tester fréquemment** : Après chaque tool, test dans Blender
3. **Itérer** : Améliorer les tools basés sur l'usage réel
4. **Documenter** : Chaque tool = docstring claire
5. **Presets early** : Les presets donnent des quick wins
6. **Macros = Magic** : Investir dans les macros, c'est LE différenciateur

---

## 🔥 Premier Prompt Complet

Voici le prompt exact pour démarrer avec Claude Code dans un dossier vide :

```
Je veux créer "Hephaestus", le meilleur MCP Blender du monde, from scratch.

Contexte :
- Un MCP permet à un LLM (comme toi) de contrôler Blender
- Architecture : Un addon Blender (bridge) + Un serveur MCP (FastMCP)
- Communication via socket JSON sur localhost:9876

Étape 1 - Structure du projet :
Crée cette structure dans le dossier actuel :

hephaestus/
├── README.md
├── pyproject.toml
├── addon.py
├── main.py
├── src/hephaestus/
│   ├── __init__.py
│   ├── server.py
│   ├── connection.py
│   └── tools/
│       ├── __init__.py
│       ├── scene.py
│       └── objects.py

Spécifications :

pyproject.toml :
- Package : hephaestus v0.1.0
- Dependencies : mcp, fastmcp
- Entry point : hephaestus = hephaestus.server:main

README.md :
- Titre : Hephaestus - Advanced Blender MCP
- Description courte
- Quick start
- Architecture overview

Ensuite, on implémentera le server et l'addon étape par étape.

Commence par créer ces fichiers squelettes.
```

---

**Voilà ! Avec ce guide, n'importe qui peut recréer Hephaestus from scratch avec Claude Code** 🔥

Le secret : **découper en étapes claires, tester fréquemment, itérer rapidement**.
