# Conformité MCP (Anthropic & JSON-RPC)

Objectif : garantir que Hephaestus MCP v2 reste strict, prévisible et conforme aux clients MCP (Claude, Codex, Smithery/Ollama).

## Règles obligatoires
- Transport : stdio uniquement pour le protocole MCP. Aucun log ni texte hors protocole sur stdout. Logs → stderr ou fichier.
- JSON-RPC 2.0 strict : `jsonrpc: "2.0"`, `id` écho, `method`, `params` objet. Erreurs avec `code`, `message`, `data` optionnel.
- Méthodes MCP : `initialize`, `listTools`, `callTool`. Pas d’effet de bord avant `initialize`.
- Tools : `name`, `description`, `inputSchema` JSON Schema. `listTools` est la source de vérité.
- Validation côté serveur : toute requête non conforme au schema est rejetée proprement, sans exécution partielle.
- Identité serveur : nom/version renseignés dans `initialize` (serverInfo).
- Erreurs métier : codes clairs (`unknown_tool`, `schema_validation_error`, `bridge_unavailable`, `tool_execution_error`), pas de traces brutes.
- Sécurité : pas d’`execute_code` par défaut ; privilégier une allowlist.

## Tests rapides de conformité
1) Santé protocole : `initialize` → `listTools` → `callTool ping` doit répondre `pong`.
2) Validation schema : `object.transform` sans `name` doit retourner une erreur de validation lisible.
3) Tool inconnu : `callTool foobar` doit renvoyer `unknown_tool`.
4) Bridge off : `scene.get_info` doit renvoyer `bridge_unavailable`.
5) Hygiène stdout : aucun bruit sur stdout ; logs visibles sur stderr/fichier.
6) Bridge socket : handshake version/token accepté ; token invalide rejeté.

## Recommandations
- Capabilities : annoncer uniquement ce qui est supporté ; pas de faux positifs.
- Timeouts/retries bridge : configurables, valeurs par défaut raisonnables.
- Logging : format structuré, niveau `INFO` par défaut, pas de secrets dans les logs.
