# Vision : Le Meilleur MCP Blender du Monde

## Analyse de l'existant

### Tools actuels (22 tools détectés)
1. **Scene & Objects**
   - get_scene_info
   - get_object_info
   - get_viewport_screenshot

2. **Code Execution**
   - execute_blender_code (très puissant mais bas niveau)

3. **Poly Haven Integration** (6+ tools)
   - get_polyhaven_categories
   - search_polyhaven_assets
   - download_polyhaven_asset
   - set_texture

4. **Hyper3D Rodin** (AI génération 3D)
   - generate_hyper3d_model_via_text
   - generate_hyper3d_model_via_images
   - poll_rodin_job_status
   - import_generated_asset

5. **Sketchfab**
   - search_sketchfab_models
   - download_sketchfab_model

6. **Hunyuan3D** (nouveau)
   - generate_hunyuan3d_model
   - poll_hunyuan_job_status
   - import_generated_asset_hunyuan

### Forces du système actuel
✅ Architecture socket simple et efficace (addon.py ↔ MCP server)
✅ Intégration d'APIs externes (Poly Haven, Hyper3D, Sketchfab, Hunyuan3D)
✅ execute_blender_code permet tout ce qui est possible en Python
✅ Screenshots pour visual feedback
✅ FastMCP utilisé (moderne)

### Faiblesses & Opportunités
❌ **Trop bas niveau** : Un LLM doit souvent coder en Python pour des opérations simples
❌ **Pas de macros/presets** : Pas de "studio lighting", "isometric camera", etc.
❌ **Pas de geometry nodes** : Très important pour le workflow moderne Blender
❌ **Pas de modifiers** : Array, Subdivision, Boolean, etc.
❌ **Animation limitée** : Pas de keyframes, timeline, etc.
❌ **Materials basiques** : Pas de node editor, shader manipulation
❌ **Pas de collections** : Organisation de scène limitée
❌ **Pas de rendering presets** : Cycles, Eevee settings
❌ **Pas de mesh editing** : Edit mode, bevels, extrusions, etc.
❌ **Pas de rigging/armatures** : Pour l'animation de personnages
❌ **Pas de particle systems** : Hair, smoke, fluids
❌ **Pas de composition** : Post-processing
❌ **Pas de batch operations** : Faire des opérations sur plusieurs objets

---

## Vision : Le MCP Blender Ultime

### Philosophie de Design
1. **Layered Approach** :
   - **L1 - High Level** : Macros intelligentes pour LLM ("create studio setup", "add dramatic lighting")
   - **L2 - Mid Level** : Operations Blender courantes (add modifier, create material, etc.)
   - **L3 - Low Level** : execute_blender_code pour cas complexes

2. **LLM-First** : Optimisé pour qu'un LLM puisse :
   - Créer des scènes complexes rapidement
   - Comprendre visuellement ce qu'il fait (screenshots++)
   - Avoir des templates/presets
   - Chaîner des opérations facilement

3. **Production-Ready** :
   - Support du workflow professionnel Blender
   - Geometry Nodes
   - Materials avancés
   - Animation
   - Rendering

---

## Architecture Proposée

### Structure des Dossiers
```
ultimate-blender-mcp/
├── addon.py                 # Bridge Blender (amélioré)
├── src/
│   ├── blender_mcp/
│   │   ├── server.py        # MCP server principal
│   │   ├── tools/           # Tous les tools organisés
│   │   │   ├── scene.py     # Scene management
│   │   │   ├── objects.py   # Object manipulation
│   │   │   ├── materials.py # Materials & shaders
│   │   │   ├── geometry_nodes.py
│   │   │   ├── modifiers.py
│   │   │   ├── animation.py
│   │   │   ├── rendering.py
│   │   │   ├── macros.py    # High-level macros
│   │   │   ├── camera.py
│   │   │   ├── lighting.py
│   │   │   ├── mesh_edit.py
│   │   │   ├── rigging.py
│   │   │   └── external_assets.py  # Poly Haven, etc.
│   │   ├── presets/         # JSON presets
│   │   │   ├── lighting/
│   │   │   ├── materials/
│   │   │   ├── camera_rigs/
│   │   │   └── scenes/
│   │   └── utils/
├── docs/
│   ├── API.md
│   ├── MACROS.md           # Documentation des macros
│   └── EXAMPLES.md         # Exemples d'usage LLM
└── tests/
```

---

## Roadmap de Tools Proposés

### Phase 1 : Core Enhancement (Fondations)

#### 1.1 Scene & Organization
- [x] get_scene_info (existe)
- [x] get_object_info (existe)
- [ ] **create_collection** (name, parent, color)
- [ ] **move_to_collection** (object, collection)
- [ ] **get_collection_tree** ()
- [ ] **duplicate_object** (object, linked=False)
- [ ] **batch_select** (pattern, type)
- [ ] **export_scene** (format, path, selection_only)

#### 1.2 Object Manipulation (Mid-Level)
- [ ] **transform_object** (object, location, rotation, scale)
- [ ] **parent_object** (child, parent, keep_transform)
- [ ] **array_objects** (object, count, offset, type="linear/circular")
- [ ] **align_objects** (objects, axis, mode="centers/bounds")
- [ ] **distribute_objects** (objects, axis, spacing)
- [ ] **snap_to_grid** (objects, size)

#### 1.3 Mesh Editing
- [ ] **enter_edit_mode** (object)
- [ ] **exit_edit_mode** ()
- [ ] **select_mesh_elements** (type="vertices/edges/faces", mode, indices)
- [ ] **extrude** (amount, direction)
- [ ] **bevel** (amount, segments, profile)
- [ ] **inset_faces** (thickness, depth)
- [ ] **loop_cut** (cuts, position)
- [ ] **merge_vertices** (mode="center/cursor/first")
- [ ] **subdivide** (cuts, smoothness)

### Phase 2 : Materials & Shading

#### 2.1 Materials
- [ ] **create_material** (name, type="principled/emission/glass")
- [ ] **assign_material** (object, material, slot)
- [ ] **set_material_property** (material, property, value)
  - Ex: base_color, metallic, roughness, emission
- [ ] **create_material_from_preset** (preset_name)
  - Presets: "gold", "chrome", "glass", "plastic", "wood", etc.
- [ ] **duplicate_material** (source, new_name)

#### 2.2 Shader Nodes (Avancé)
- [ ] **add_shader_node** (material, node_type, location)
- [ ] **connect_shader_nodes** (material, from_node, to_node, from_socket, to_socket)
- [ ] **create_pbr_setup** (material, textures_dict)
  - Auto-setup Base Color, Normal, Roughness, Metallic maps
- [ ] **add_texture_node** (material, texture_path, node_name)

### Phase 3 : Geometry Nodes

#### 3.1 Geometry Nodes
- [ ] **add_geometry_nodes_modifier** (object, name)
- [ ] **create_geometry_node_group** (name)
- [ ] **add_geometry_node** (group, node_type, location)
- [ ] **connect_geometry_nodes** (group, from_node, to_node, from_socket, to_socket)
- [ ] **apply_geometry_nodes_preset** (object, preset)
  - Presets: "scatter_on_surface", "curve_to_mesh", "array_on_curve", etc.

### Phase 4 : Modifiers

#### 4.1 Modifiers
- [ ] **add_modifier** (object, type, name, params)
  - Types: Array, Mirror, Solidify, Subdivision, Boolean, Bevel, etc.
- [ ] **modify_modifier** (object, modifier_name, params)
- [ ] **apply_modifier** (object, modifier_name)
- [ ] **remove_modifier** (object, modifier_name)

#### 4.2 Boolean Operations
- [ ] **boolean_operation** (object_a, object_b, operation="union/difference/intersect")
- [ ] **batch_boolean** (target, objects, operation)

### Phase 5 : Animation

#### 5.1 Keyframes & Timeline
- [ ] **set_keyframe** (object, property, frame, value)
- [ ] **get_animation_data** (object)
- [ ] **set_frame_range** (start, end)
- [ ] **set_current_frame** (frame)
- [ ] **animate_property** (object, property, keyframes_dict)
  - Ex: {0: 0, 50: 10, 100: 0} pour location.x

#### 5.2 Animation Presets
- [ ] **create_camera_fly_through** (camera, path_points, duration)
- [ ] **animate_rotation** (object, axis, degrees, duration)
- [ ] **bounce_animation** (object, height, duration, bounces)

### Phase 6 : Camera & Rendering

#### 6.1 Camera
- [ ] **create_camera** (name, location, rotation)
- [ ] **point_camera_at** (camera, target_object/location)
- [ ] **set_camera_orthographic** (camera, scale)
- [ ] **set_camera_perspective** (camera, focal_length)
- [ ] **create_camera_rig** (type="orbit/follow/rail")

#### 6.2 Rendering
- [ ] **set_render_engine** (engine="cycles/eevee/workbench")
- [ ] **set_render_resolution** (x, y, percentage)
- [ ] **set_render_samples** (samples)
- [ ] **render_image** (filepath, camera)
- [ ] **render_animation** (filepath, camera, frame_range)
- [ ] **apply_render_preset** (preset)
  - Presets: "preview", "high_quality", "4k_production", etc.

### Phase 7 : Lighting

#### 7.1 Lights
- [ ] **create_light** (type="point/sun/spot/area", name, location, energy)
- [ ] **set_light_color** (light, color, temperature)
- [ ] **set_hdri** (hdri_path, rotation, strength)

#### 7.2 Lighting Presets (HIGH VALUE pour LLM!)
- [ ] **apply_lighting_preset** (preset)
  - **"three_point"** : Classic 3-point lighting
  - **"studio"** : Studio lighting setup
  - **"sunset"** : Sunset ambiance
  - **"dramatic"** : High contrast dramatic
  - **"soft"** : Soft diffuse lighting
  - **"outdoor"** : HDRI outdoor

### Phase 8 : Macros Ultra High-Level (GAME CHANGER!)

#### 8.1 Scene Presets
- [ ] **create_product_showcase** (object, style="minimal/studio/dramatic")
  - Auto : camera isométrique, lighting 3-point, floor plane, matériaux
- [ ] **create_environment** (type="forest/desert/urban/space", size)
  - Utilise assets + scatter + lighting
- [ ] **create_character_rig_setup** (mesh_object)
  - Auto-rig basic avec Rigify

#### 8.2 Smart Operations
- [ ] **auto_texture_from_image** (object, image_path)
  - Analyse l'image, crée materials, unwrap, projette
- [ ] **create_text_3d** (text, font, extrude, bevel)
- [ ] **scatter_objects_on_surface** (target_surface, scatter_object, count, scale_range)
- [ ] **procedural_city** (size, density, height_range)

#### 8.3 Analysis & Suggestions
- [ ] **analyze_scene** ()
  - Retourne: poly count, materials used, lighting setup, suggestions
- [ ] **suggest_improvements** ()
  - "Scene is too dark", "Add subsurface to subdivision modifier", etc.
- [ ] **auto_optimize_scene** ()
  - Décime meshes, optimise modifiers, merge materials

### Phase 9 : Particle Systems & Physics
- [ ] **add_particle_system** (object, type="hair/emitter", settings)
- [ ] **add_physics** (object, type="rigid_body/cloth/soft_body", settings)
- [ ] **bake_simulation** (start_frame, end_frame)

---

## Features Différentiantes (vs MCP actuel)

### 1. Preset System
JSON presets pour tout :
```json
// presets/lighting/three_point.json
{
  "name": "Three Point Lighting",
  "lights": [
    {"type": "area", "location": [5, -5, 5], "energy": 1000, "role": "key"},
    {"type": "area", "location": [-3, -5, 3], "energy": 300, "role": "fill"},
    {"type": "area", "location": [0, 5, 2], "energy": 100, "role": "rim"}
  ],
  "world_settings": {"ambient": 0.1}
}
```

### 2. Visual Feedback Enhanced
- [ ] **get_wireframe_screenshot** ()
- [ ] **get_material_preview** (material)
- [ ] **get_render_preview** (quick=True)
- [ ] **highlight_objects** (objects) puis screenshot

### 3. Workflow Helpers
- [ ] **undo** (steps=1)
- [ ] **redo** (steps=1)
- [ ] **save_blend_file** (path)
- [ ] **version_save** () (incremental save)

### 4. Smart Defaults
Chaque tool a des smart defaults optimisés pour LLM usage :
- `create_camera(type="product")` → auto position isométrique
- `add_light(preset="soft")` → area light optimale
- `create_material(type="metal")` → metallic=1.0, roughness=0.3

### 5. Documentation LLM-Friendly
Chaque tool a :
- Description claire
- Exemples d'usage
- Common use cases
- Visual examples (images dans docs/)

---

## Stack Technique

### Backend
- **FastMCP** (déjà utilisé) ✅
- **Pydantic** pour validation des paramètres
- **asyncio** pour opérations longues (render, simulation)
- **Cache** pour presets (chargés une fois)

### Addon Blender
- **Threading** pour ne pas bloquer UI
- **Progress callback** pour opérations longues
- **Error handling** robuste avec rollback

### Testing
- **pytest** pour tests unitaires
- **Blender headless** pour tests d'intégration
- **Golden files** pour tests visuels (compare rendus)

---

## Priorisation des Phases

### MVP (Minimum Viable Product) - 2 semaines
**Phase 1** + **Phase 7.2 (Lighting Presets)** + **Phase 8.1 (Scene Presets basics)**
→ Permet déjà des créations impressionnantes

### V1.0 - 1 mois
MVP + **Phase 2** (Materials) + **Phase 4** (Modifiers) + **Phase 6** (Camera/Rendering)
→ Workflow complet pour product visualization

### V2.0 - 2-3 mois
V1.0 + **Phase 3** (Geometry Nodes) + **Phase 5** (Animation) + **Phase 8.2** (Smart Ops)
→ Production-ready pour motion design

### V3.0+ - Long terme
**Phase 9** (Physics) + Rigging avancé + Composition + AI improvements

---

## Métriques de Succès

1. **Nombre de tools** : 100+ (vs 22 actuellement)
2. **Niveau d'abstraction** : 70% high/mid level, 30% low level
3. **Rapidité création scène** : LLM peut créer une scène complexe en <10 tools calls
4. **Documentation** : 100% tools documentés avec exemples
5. **Community** : Templates partagés par users

---

## Cas d'Usage Cibles

### Product Visualization
LLM : "Create a product showcase for a watch"
→ Auto : camera, lighting 3-point, turntable animation, render settings

### Architecture Visualization
LLM : "Create an interior scene with furniture"
→ Scatter objects, HDRI lighting, camera walkthrough

### Character Animation
LLM : "Import this character and make it wave"
→ Auto-rig, IK setup, animation

### Motion Graphics
LLM : "Create an animated logo reveal"
→ Text 3D, animation presets, particles, render

### Environment Art
LLM : "Create a forest scene"
→ Scatter trees (from Poly Haven), terrain, fog, HDRI

---

## Innovations Uniques

### 1. AI-Powered Suggestions
Le MCP analyse la scène et suggère :
- "This object could benefit from a bevel modifier"
- "Lighting is flat, try adding a rim light"
- "Materials are basic, want me to add roughness variation?"

### 2. Template Library
Users peuvent sauvegarder leurs setups :
```python
save_template("my_studio_setup", include=["cameras", "lights", "render_settings"])
load_template("my_studio_setup")
```

### 3. Batch Intelligence
```python
batch_apply_operation(
    objects=["Cube.001", "Cube.002", "Cube.003"],
    operation="add_modifier",
    params={"type": "subdivision", "levels": 2}
)
```

### 4. Contextual Tools
Le MCP détecte le contexte et adapte les suggestions :
- Si obj sélectionné → suggère modifiers appropriés
- Si en edit mode → suggère mesh ops
- Si animation → suggère keyframe tools

---

## Questions pour Décisions

1. **Garder l'existant ?**
   - ✅ Garder : Architecture socket, FastMCP, external APIs
   - 🔄 Refactor : Organisation des tools, presets system
   - ❌ Remplacer : Rien, tout peut être amélioré

2. **Priorité #1 ?**
   - Option A : Macros high-level (quick wins, impressionnant)
   - Option B : Foundations solides (mesh edit, materials)
   - **Recommandation** : Mix → MVP avec macros + core foundations

3. **External Assets ?**
   - Garder Poly Haven, Sketchfab, Hyper3D ✅
   - Ajouter : Quixel Megascans ? Blenderkit ? AmbientCG ?

4. **Telemetry ?**
   - Garder pour amélioration continue ✅
   - Rendre opt-in par défaut

---

## Next Steps Immédiats

1. **Valider cette vision** avec toi
2. **Prioriser** les phases ensemble
3. **Créer structure** de dossiers
4. **Implémenter MVP** :
   - Collections management
   - Object transform helpers
   - Lighting presets (3-point, studio)
   - Material presets
   - Product showcase macro
5. **Tester** avec vrais use cases
6. **Itérer** !

---

**Ce MCP sera THE reference pour Blender + LLM workflows** 🚀

Tu as des préférences ? Des features qui te semblent critiques ?
