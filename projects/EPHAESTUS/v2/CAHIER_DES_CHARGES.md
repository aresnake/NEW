# Hephaestus V2 - Cahier des charges

## Vision
Construire le meilleur MCP Blender du monde: stable, pro, multi-LLM, securise, maintenable, et simple a installer.

## Objectifs produit
- Controle fiable de Blender via MCP (JSON-RPC strict, stdio).
- Multi-LLM: Claude Desktop/Code, GPT web, Ollama, autres clients MCP.
- Installation en 1 minute (Windows first), docs claires.
- Qualite pro: tests, logs propres, versioning, compat Blender.

## Non-objectifs (pour V2.0)
- UI complexe dans Blender.
- Support reseau distant par defaut (local only).
- Exposition internet sans securite forte.

## Normes et protocoles
- MCP officiel: initialize, listTools, callTool, protocolVersion, capabilities.
- JSON-RPC 2.0 strict (erreurs et codes standardises).
- stdout reserve aux messages MCP; logs sur stderr ou fichier.

## Architecture cible (dans v2/)
- v2/mcp/        : serveur MCP pur (stdio), mapping tools, schema validation.
- v2/addon/      : addon Blender multi-fichiers, propre, testable.
- v2/bridge/     : transport (socket/IPC), framing, retries, timeouts.
- v2/shared/     : types, erreurs, schemas, constants.
- v2/docs/       : spec, API, compat, install, quickstart.
- v2/tests/      : unit + e2e (MCP -> Blender).
- v2/scripts/    : QA unique + utilitaires.

## Principes de design
- Separation stricte des couches (MCP, bridge, addon, domain).
- Reponses standardisees: {ok, data, error, meta}.
- Compat Blender 3.x/4.x/5.x avec detection auto.
- Aucun effet de bord avant initialize.

## Securite
- execute_code: desactive par defaut (opt-in explicite).
- Token local optionnel pour le bridge.
- Allowlist d'outils par client si possible.

## Qualite et tests
- Tests unitaires sur schemas, mapping tools, validation params.
- Test e2e minimal (mock ou Blender headless si possible).
- Logs structurels + niveaux coherents.

## Experience dev
- Hot reload addon (script utilitaire).
- Config via fichier + variables d'environnement.
- Pas de hardcode (ports, timeouts, chemins).

## Migration depuis V1
- V2 vit dans v2/ sans casser V1.
- Migration progressive tool par tool.
- Garder un tableau de compat (V1 vs V2).

## Livrables V2.0
- Serveur MCP stable et conforme.
- Addon propre (multi-fichiers).
- QA unique (Ollama) + report JSON/MD.
- Docs install + API + quickstart.
- Release package (zip addon + pip package).

## Definition of Done
- initialize/listTools/callTool fonctionnels.
- 10 tools critiques portes et testes.
- Log propre (pas de bruit sur stdout).
- Install guide teste sur Windows.

