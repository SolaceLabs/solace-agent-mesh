# Changelog

## [1.21.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.5...1.21.0) (2026-04-29)


### Features

* **DATAGO-131493:** User can run the experiment and view the result ([#1473](https://github.com/SolaceLabs/solace-agent-mesh/issues/1473)) ([a42a3f5](https://github.com/SolaceLabs/solace-agent-mesh/commit/a42a3f5c60ab5229555ef2246cbe10c39872d70a))


### Bug Fixes

* **DATAGO-134139:** stop cascading auth prompts in solace-chat's Atlassian heavy-query flow ([#1474](https://github.com/SolaceLabs/solace-agent-mesh/issues/1474)) ([18e7386](https://github.com/SolaceLabs/solace-agent-mesh/commit/18e7386b190faa9beceab10b26907846f3e4f40b))

## [1.20.5](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.4...1.20.5) (2026-04-28)


### Bug Fixes

* **DATAGO-133254:** fixing minor UX issues. ([#1445](https://github.com/SolaceLabs/solace-agent-mesh/issues/1445)) ([c322084](https://github.com/SolaceLabs/solace-agent-mesh/commit/c322084da33bc772c057d9a31e3eb0dedcaca199))
* **DATAGO-134083:** Fix cryptic code rendering for citations during response streaming in projects ([#1468](https://github.com/SolaceLabs/solace-agent-mesh/issues/1468)) ([b75ead3](https://github.com/SolaceLabs/solace-agent-mesh/commit/b75ead325e409a3def350b4688fabd52fff247de))
* **DATAGO-134087:** Audit and optimize Database indexing for performance ([#1469](https://github.com/SolaceLabs/solace-agent-mesh/issues/1469)) ([d235de2](https://github.com/SolaceLabs/solace-agent-mesh/commit/d235de24164056504ca772ae37ef395d76ac3927))

## [1.20.4](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.3...1.20.4) (2026-04-28)


### Bug Fixes

* **DATAGO-123668:** Implement verification step in deep research process ([#1307](https://github.com/SolaceLabs/solace-agent-mesh/issues/1307)) ([7b90384](https://github.com/SolaceLabs/solace-agent-mesh/commit/7b90384c4c2ac0e57c3f52302fdf8d560f9574dc))
* **DATAGO-131321:** expose useAllArtifacts ([#1465](https://github.com/SolaceLabs/solace-agent-mesh/issues/1465)) ([7f47c93](https://github.com/SolaceLabs/solace-agent-mesh/commit/7f47c93ff59c9d0f25504990438be4eae27641eb))
* **DATAGO-133564:** Fix 'Stop' button cutoff in narrow chat window ([#1455](https://github.com/SolaceLabs/solace-agent-mesh/issues/1455)) ([eb84685](https://github.com/SolaceLabs/solace-agent-mesh/commit/eb84685bad183e0d057c28d71c9f4c744bf8e45b))
* **DATAGO-133950:** forward unknown attrs through ADK's session-service wrappers ([#1462](https://github.com/SolaceLabs/solace-agent-mesh/issues/1462)) ([8e0a5d4](https://github.com/SolaceLabs/solace-agent-mesh/commit/8e0a5d45a237d576423940a5d6b27f8531183b64))
* **DATAGO-133967:** SSE viz queue overflow under high-fan-out tasks — UI progress freezes/skips events ([#1464](https://github.com/SolaceLabs/solace-agent-mesh/issues/1464)) ([4c8df84](https://github.com/SolaceLabs/solace-agent-mesh/commit/4c8df84a8470d931759eecaca67423a7ce460779))

## [1.20.3](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.2...1.20.3) (2026-04-27)


### Bug Fixes

* **DATAGO-133911:** SSE event replay silently disabled — gateway logs "Database not configured" despite SQL session_service ([#1458](https://github.com/SolaceLabs/solace-agent-mesh/issues/1458)) ([abb5c6c](https://github.com/SolaceLabs/solace-agent-mesh/commit/abb5c6cf603fa263918e8653b67cd6b51de82557))
* **DATAGO-133916 :** extract_content_from_artifact spends 10-14 min per call summarising 35-66KB JSON ([#1460](https://github.com/SolaceLabs/solace-agent-mesh/issues/1460)) ([80ac170](https://github.com/SolaceLabs/solace-agent-mesh/commit/80ac170e84d784f892ccb1cb5e480a027b7ded93))

## [1.20.2](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.1...1.20.2) (2026-04-26)


### Bug Fixes

* **DATAGO-133775:** Fix authentication failure for scheduled SAM reports against Salesforce ([#1456](https://github.com/SolaceLabs/solace-agent-mesh/issues/1456)) ([cd39424](https://github.com/SolaceLabs/solace-agent-mesh/commit/cd3942425033cf3a7dc5a820064e9b3e5d1e7891))

## [1.20.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.20.0...1.20.1) (2026-04-25)


### Bug Fixes

* **DATAGO-131321:** enhance visualizer step cards ([#1452](https://github.com/SolaceLabs/solace-agent-mesh/issues/1452)) ([091f987](https://github.com/SolaceLabs/solace-agent-mesh/commit/091f9876982e958f8119e5a3c94e2307e8d70bef))
* **DATAGO-131500:** Resolve model override for agent's own model alias ([#1438](https://github.com/SolaceLabs/solace-agent-mesh/issues/1438)) ([44e5dce](https://github.com/SolaceLabs/solace-agent-mesh/commit/44e5dceb7d39131c36a4be57f353754f72499aa2))
* **DATAGO-133094:** reducing status calls ([#1442](https://github.com/SolaceLabs/solace-agent-mesh/issues/1442)) ([18ef571](https://github.com/SolaceLabs/solace-agent-mesh/commit/18ef571ec27411e34e5690fd531bd9dd050ff143))
* **DATAGO-133559:** Context usage indicator inflates after tasks with peer delegation ([#1453](https://github.com/SolaceLabs/solace-agent-mesh/issues/1453)) ([9658450](https://github.com/SolaceLabs/solace-agent-mesh/commit/96584509304ea2834b199c0be2ab0d8415643514))

## [1.20.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.19.1...1.20.0) (2026-04-24)


### Features

* **DATAGO-113923:** real-time context usage indicator in chat with multiple metrics ([#1236](https://github.com/SolaceLabs/solace-agent-mesh/issues/1236)) ([d2c25fc](https://github.com/SolaceLabs/solace-agent-mesh/commit/d2c25fc8083b0816fe5b1d50372db77de8a93b46))

## [1.19.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.19.0...1.19.1) (2026-04-23)


### Bug Fixes

* **DATAGO-131964:** Investigate delay and visibility issues for scheduled tasks in recent chats ([#1394](https://github.com/SolaceLabs/solace-agent-mesh/issues/1394)) ([79a2ae4](https://github.com/SolaceLabs/solace-agent-mesh/commit/79a2ae4c926a51185f2e8fb0eb8df8898959655e))


### Documentation

* **DATAGO-132664:** Restructure Teams gateway setup with Microsoft guide references ([#1437](https://github.com/SolaceLabs/solace-agent-mesh/issues/1437)) ([2487100](https://github.com/SolaceLabs/solace-agent-mesh/commit/24871002256ec0cda9584e7fca972c693fb51fdf))

## [1.19.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.18.40...1.19.0) (2026-04-21)


### Features

* **DATAGO-132352:** ensure trailing slashes on api_base are handled correctly ([#1412](https://github.com/SolaceLabs/solace-agent-mesh/issues/1412)) ([4a6886d](https://github.com/SolaceLabs/solace-agent-mesh/commit/4a6886d3cdc86f7e03d84cdb6df8a6818bdae44a))


### Bug Fixes

* **DATAGO-118906:** Update installation documentation for SAM ([#1416](https://github.com/SolaceLabs/solace-agent-mesh/issues/1416)) ([5494b53](https://github.com/SolaceLabs/solace-agent-mesh/commit/5494b5309a38c2b9e464f6547acb9fd0c1bc3833))
* **DATAGO-132190:** add min-w-0 to main to prevent nav sidebar collapse ([#1422](https://github.com/SolaceLabs/solace-agent-mesh/issues/1422)) ([9a2f130](https://github.com/SolaceLabs/solace-agent-mesh/commit/9a2f130da2c905a7bf03b0bdd68e94af3eece230))
* **DATAGO-132190:** exclude test-utils from tsconfig.lib.json ([#1419](https://github.com/SolaceLabs/solace-agent-mesh/issues/1419)) ([2e8e93f](https://github.com/SolaceLabs/solace-agent-mesh/commit/2e8e93fb9ca65d977d7d8c934dcf1f54d97fdf16))
* **DATAGO-132511:** investigate intermittent hanging integration tests ([#1417](https://github.com/SolaceLabs/solace-agent-mesh/issues/1417)) ([1b14bfe](https://github.com/SolaceLabs/solace-agent-mesh/commit/1b14bfe159ce1e14a41e4be4446327eb71e65f47))
* **DATAGO-132719:** Shared chat tool calls are empty and crash on clicks ([#1425](https://github.com/SolaceLabs/solace-agent-mesh/issues/1425)) ([5fcddbb](https://github.com/SolaceLabs/solace-agent-mesh/commit/5fcddbb3bf9049d3669f444ed085011e1d27d78d))

## [1.19.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.18.39...1.19.0) (2026-04-21)


### Features

* **DATAGO-132352:** ensure trailing slashes on api_base are handled correctly ([#1412](https://github.com/SolaceLabs/solace-agent-mesh/issues/1412)) ([4a6886d](https://github.com/SolaceLabs/solace-agent-mesh/commit/4a6886d3cdc86f7e03d84cdb6df8a6818bdae44a))


### Bug Fixes

* **DATAGO-118906:** Update installation documentation for SAM ([#1416](https://github.com/SolaceLabs/solace-agent-mesh/issues/1416)) ([5494b53](https://github.com/SolaceLabs/solace-agent-mesh/commit/5494b5309a38c2b9e464f6547acb9fd0c1bc3833))
* **DATAGO-132190:** add min-w-0 to main to prevent nav sidebar collapse ([#1422](https://github.com/SolaceLabs/solace-agent-mesh/issues/1422)) ([9a2f130](https://github.com/SolaceLabs/solace-agent-mesh/commit/9a2f130da2c905a7bf03b0bdd68e94af3eece230))
* **DATAGO-132190:** exclude test-utils from tsconfig.lib.json ([#1419](https://github.com/SolaceLabs/solace-agent-mesh/issues/1419)) ([2e8e93f](https://github.com/SolaceLabs/solace-agent-mesh/commit/2e8e93fb9ca65d977d7d8c934dcf1f54d97fdf16))
* **DATAGO-132333:** bump solace-ai-connector to 3.3.10 ([#1411](https://github.com/SolaceLabs/solace-agent-mesh/issues/1411)) ([3bff9f9](https://github.com/SolaceLabs/solace-agent-mesh/commit/3bff9f92b32b5ffee5061908aaf600f4d37c10ea))
* **DATAGO-132511:** investigate intermittent hanging integration tests ([#1417](https://github.com/SolaceLabs/solace-agent-mesh/issues/1417)) ([1b14bfe](https://github.com/SolaceLabs/solace-agent-mesh/commit/1b14bfe159ce1e14a41e4be4446327eb71e65f47))
* **DATAGO-132719:** Shared chat tool calls are empty and crash on clicks ([#1425](https://github.com/SolaceLabs/solace-agent-mesh/issues/1425)) ([5fcddbb](https://github.com/SolaceLabs/solace-agent-mesh/commit/5fcddbb3bf9049d3669f444ed085011e1d27d78d))
