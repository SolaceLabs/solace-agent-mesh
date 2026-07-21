# Changelog

## [1.28.5](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.28.4...1.28.5) (2026-07-21)


### Bug Fixes

* **DATAGO-138845:** handle async session DB engine in readiness health check ([#1605](https://github.com/SolaceLabs/solace-agent-mesh/issues/1605)) ([b7ce8cc](https://github.com/SolaceLabs/solace-agent-mesh/commit/b7ce8cc28b9b789e15614b9dbf78169d62534d58))
* **DATAGO-138845:** upgrade google-adk to 2.5.0 to fix starlette CVEs ([#1602](https://github.com/SolaceLabs/solace-agent-mesh/issues/1602)) ([4c96454](https://github.com/SolaceLabs/solace-agent-mesh/commit/4c96454f7660201c12441e92e9ef9e7a8e0b39aa))
* **DATAGO-144737:** bump pillow to 12.3.0 (9 CVEs) ([#1609](https://github.com/SolaceLabs/solace-agent-mesh/issues/1609)) ([42263c6](https://github.com/SolaceLabs/solace-agent-mesh/commit/42263c66d24812ad5b5add1cb233ee67b73c67c8))
* **DATAGO-144858:** bump mcp to 1.28.1 for CVE-2026-59950/52870/52869 ([#1607](https://github.com/SolaceLabs/solace-agent-mesh/issues/1607)) ([49ee1ea](https://github.com/SolaceLabs/solace-agent-mesh/commit/49ee1ea79d90d73a9548e9e963a18754a76da518))
* **DATAGO-145006:** bump httplib2 to 0.32.0 for CVE-2026-59939 ([#1611](https://github.com/SolaceLabs/solace-agent-mesh/issues/1611)) ([e0657ce](https://github.com/SolaceLabs/solace-agent-mesh/commit/e0657ce9980ebba08735c0b87d732505c68f5aac))
* **DATAGO-145007:** bump python-liquid to 2.2.1 for CVE-2026-55865 ([#1608](https://github.com/SolaceLabs/solace-agent-mesh/issues/1608)) ([2d34625](https://github.com/SolaceLabs/solace-agent-mesh/commit/2d346255b1bc871b1fd01aa8c4f559d595163f8f))
* **DATAGO-145096:** bump joserfc to 1.7.4 for CVE-2026-49852 ([#1612](https://github.com/SolaceLabs/solace-agent-mesh/issues/1612)) ([8080e00](https://github.com/SolaceLabs/solace-agent-mesh/commit/8080e001fd09ba39c2fed304862193199b1b2dbe))
* **DATAGO-145097:** bump soupsieve to 2.8.4 for CVE-2026-49476, CVE-2026-49477 ([#1610](https://github.com/SolaceLabs/solace-agent-mesh/issues/1610)) ([336e724](https://github.com/SolaceLabs/solace-agent-mesh/commit/336e72459e78daea683539c24fc4583e3fde47ba))


### Reverts

* **DATAGO-138845:** roll back google-adk 2.5.0 ([#1602](https://github.com/SolaceLabs/solace-agent-mesh/issues/1602)) and readiness fix ([#1605](https://github.com/SolaceLabs/solace-agent-mesh/issues/1605)) ([#1606](https://github.com/SolaceLabs/solace-agent-mesh/issues/1606)) ([6b49f10](https://github.com/SolaceLabs/solace-agent-mesh/commit/6b49f10c247fb572915aa40b04050369386b053b))


### Documentation

* deprecate legacy 1.x docs site with version notice and noindex (DATAGO-139020) ([#1601](https://github.com/SolaceLabs/solace-agent-mesh/issues/1601)) ([2b98c7a](https://github.com/SolaceLabs/solace-agent-mesh/commit/2b98c7a68763c8bec392dbf209ed2d583c352bc9))

## [1.28.4](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.28.3...1.28.4) (2026-06-29)


### Bug Fixes

* **security:** patch Critical/High dependency vulnerabilities ([#1597](https://github.com/SolaceLabs/solace-agent-mesh/issues/1597)) ([95048d0](https://github.com/SolaceLabs/solace-agent-mesh/commit/95048d0252a3dbd9e64253e560b124e21e9e3603))

## [1.28.3](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.28.2...1.28.3) (2026-06-19)


### Bug Fixes

* **DATAGO-139037:** bump Python deps + image OS packages to clear vulnerability CVEs ([#1587](https://github.com/SolaceLabs/solace-agent-mesh/issues/1587)) ([475ff56](https://github.com/SolaceLabs/solace-agent-mesh/commit/475ff561280be16570174118431ac8aec2be7341))
* **DATAGO-141037:** re-validate SSRF guard on every connection in web_request ([#1592](https://github.com/SolaceLabs/solace-agent-mesh/issues/1592)) ([40202f1](https://github.com/SolaceLabs/solace-agent-mesh/commit/40202f12bb48c74d043a2dc1afbc6a25de7653eb))
* **security:** upgrade turbo-stream to 3.0.0 (CVE-2026-3407) ([#1595](https://github.com/SolaceLabs/solace-agent-mesh/issues/1595)) ([271646d](https://github.com/SolaceLabs/solace-agent-mesh/commit/271646d7e13b18e68a02536afa0e9035fedce646))

## [1.28.2](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.28.1...1.28.2) (2026-06-04)


### Bug Fixes

* **auth:** skip sentinel claim values when extracting user identifier ([#1584](https://github.com/SolaceLabs/solace-agent-mesh/issues/1584)) ([f4ffde6](https://github.com/SolaceLabs/solace-agent-mesh/commit/f4ffde68facae594f095040e52fcbb5ddb940121))

## [1.28.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.28.0...1.28.1) (2026-06-04)


### Bug Fixes

* **DATAGO-138636:** backfill agent id for chat sessions starting with artifact uploads ([#1580](https://github.com/SolaceLabs/solace-agent-mesh/issues/1580)) ([4699068](https://github.com/SolaceLabs/solace-agent-mesh/commit/4699068e0e7289dd475f5f52162431862315abb7))
* **DATAGO-138846:** bump pyjwt, react-router-dom, @remix-run/*, openssl to clear CVEs ([#1583](https://github.com/SolaceLabs/solace-agent-mesh/issues/1583)) ([56c6f16](https://github.com/SolaceLabs/solace-agent-mesh/commit/56c6f16b7c7e26f813bd1d9e5f002edf908448b6))

## [1.28.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.27.1...1.28.0) (2026-06-02)


### Features

* Rename embedded chat surface route from /embed to /agent-mode ([#1578](https://github.com/SolaceLabs/solace-agent-mesh/issues/1578)) ([91322d4](https://github.com/SolaceLabs/solace-agent-mesh/commit/91322d4ba68e857891f7446bbd94c72047c19336))

## [1.27.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.27.0...1.27.1) (2026-06-02)


### Bug Fixes

* **DATAGO-138153:** removing speech settings from embedded view ([#1576](https://github.com/SolaceLabs/solace-agent-mesh/issues/1576)) ([1690565](https://github.com/SolaceLabs/solace-agent-mesh/commit/16905656a8a2b2f9b5b665371b349708c5a7bfa1))

## [1.27.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.26.1...1.27.0) (2026-06-02)


### Features

* **DATAGO-138153:** Adding embedded agent mode ([#1574](https://github.com/SolaceLabs/solace-agent-mesh/issues/1574)) ([1adc5eb](https://github.com/SolaceLabs/solace-agent-mesh/commit/1adc5eb82547376c09189681d7bbf6d92336c627))


### Bug Fixes

* **DATAGO-130049:** workflow node agents hallucinate tool name instead of using inline artifact block ([#1551](https://github.com/SolaceLabs/solace-agent-mesh/issues/1551)) ([38d337c](https://github.com/SolaceLabs/solace-agent-mesh/commit/38d337c275c8e234cbecedcf43228fc2f1cc58ae))

## [1.26.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.26.0...1.26.1) (2026-05-25)


### Bug Fixes

* **DATAGO-132491:** bump mako to 1.3.12 for security vulnerabilities ([#1554](https://github.com/SolaceLabs/solace-agent-mesh/issues/1554)) ([cc1a845](https://github.com/SolaceLabs/solace-agent-mesh/commit/cc1a845eac38156d4567b11d4c56c652cac69337))
* **DATAGO-134066:** bump authlib to 1.6.12+ for CVE-2026-41425, CVE-2026-44681 ([#1559](https://github.com/SolaceLabs/solace-agent-mesh/issues/1559)) ([ea29b0d](https://github.com/SolaceLabs/solace-agent-mesh/commit/ea29b0d45dfb8d3c7149f2c0b8123207c728a90a))
* **DATAGO-135330:** upgrade pip to 26.1+ for CVE-2026-6357, CVE-2026-3219 ([#1562](https://github.com/SolaceLabs/solace-agent-mesh/issues/1562)) ([35ff2d1](https://github.com/SolaceLabs/solace-agent-mesh/commit/35ff2d14f791f35e48af6a6ef10b30e0166f9013))
* **DATAGO-135331:** bump npm to 11.15.0 for CVE-2026-42338, CVE-2026-45149 ([#1561](https://github.com/SolaceLabs/solace-agent-mesh/issues/1561)) ([59768b9](https://github.com/SolaceLabs/solace-agent-mesh/commit/59768b98f73060d066850d40da71035e4b3c85e5))
* **DATAGO-136672:** bump python-liquid to 2.2.0 for CVE-2026-45017 ([#1557](https://github.com/SolaceLabs/solace-agent-mesh/issues/1557)) ([35c0b14](https://github.com/SolaceLabs/solace-agent-mesh/commit/35c0b145ecfc7f8bc2a03ab8cf16fcb13733818a))
* **DATAGO-136970:** bump ffmpeg to 7.1.4 for CVE-2026-40962 ([#1556](https://github.com/SolaceLabs/solace-agent-mesh/issues/1556)) ([852d0e6](https://github.com/SolaceLabs/solace-agent-mesh/commit/852d0e60dbd8dd4e52307ffdffe9bb44f20f0a72))
* **DATAGO-137348:** bump idna to 3.15 for CVE-2026-45409 ([#1560](https://github.com/SolaceLabs/solace-agent-mesh/issues/1560)) ([d5a2c31](https://github.com/SolaceLabs/solace-agent-mesh/commit/d5a2c31307dabfb49702df33cf5e0d0dcb58963f))
* **DATAGO-137349:** pin libcap2 to 1:2.75-10+deb13u1+b1 for CVE-2026-4878 ([#1558](https://github.com/SolaceLabs/solace-agent-mesh/issues/1558)) ([3cb0c3c](https://github.com/SolaceLabs/solace-agent-mesh/commit/3cb0c3c74fd41214b4727c8eaca27d7a4f885730))

## [1.26.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.25.1...1.26.0) (2026-05-21)


### Features

* **DATAGO-135978:** Revert model configuration - optionally allow model setup in sam init --gui ([#1532](https://github.com/SolaceLabs/solace-agent-mesh/issues/1532)) ([03c630a](https://github.com/SolaceLabs/solace-agent-mesh/commit/03c630a71cc20ac6aa5bef3df57a0791846b20c4))


### Bug Fixes

* **ci:** bump libc6 pin to 2.41-12+deb13u3 to unblock Docker build ([#1548](https://github.com/SolaceLabs/solace-agent-mesh/issues/1548)) ([b19a896](https://github.com/SolaceLabs/solace-agent-mesh/commit/b19a8969c2713f1e405cc64106d287e4eaba6c49))
* **DATAGO-134649:** sort litellm fallback model list for OpenAI provider ([#1541](https://github.com/SolaceLabs/solace-agent-mesh/issues/1541)) ([3118fa7](https://github.com/SolaceLabs/solace-agent-mesh/commit/3118fa717678ea15ae464ccb7375d26973943573))
* **DATAGO-136673:** bump python-multipart, mako, solace-ai-connector for vuln fixes ([#1549](https://github.com/SolaceLabs/solace-agent-mesh/issues/1549)) ([00f6a35](https://github.com/SolaceLabs/solace-agent-mesh/commit/00f6a35071171d42c6f87a625e597812bb894268))
* **DATAGO-136753:** Missing RBAC handling and documentation on model config endpoints ([#1540](https://github.com/SolaceLabs/solace-agent-mesh/issues/1540)) ([47ee6cf](https://github.com/SolaceLabs/solace-agent-mesh/commit/47ee6cfc37b9a3b11a567a63f5561c4827209bec))
* **DATAGO-137421:** WebUI slow due to S3 connection pool exhaustion on /api/v1/artifacts/all ([#1550](https://github.com/SolaceLabs/solace-agent-mesh/issues/1550)) ([4c15cf3](https://github.com/SolaceLabs/solace-agent-mesh/commit/4c15cf30ba65f10e58039dce1da5ec0f5d5bf418))


### Documentation

* **DATAGO-136350:** default EVAL_DATA_BUCKET_NAME so Quickstart K8s installs retain eval artifacts ([#1531](https://github.com/SolaceLabs/solace-agent-mesh/issues/1531)) ([d2ff4f8](https://github.com/SolaceLabs/solace-agent-mesh/commit/d2ff4f8cdc32acba2e9603b5696d8b8fe4a26b03))

## [1.25.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.25.0...1.25.1) (2026-05-13)


### Bug Fixes

* **DATAGO-125452:** cleanup cypress tests rc ([#1478](https://github.com/SolaceLabs/solace-agent-mesh/issues/1478)) ([7bf6e07](https://github.com/SolaceLabs/solace-agent-mesh/commit/7bf6e07d9a99b9f9a1730c560b5b1cfce3f16189))
* **DATAGO-134384:** Updated Scheduled Tasks based on UX feedback ([#1481](https://github.com/SolaceLabs/solace-agent-mesh/issues/1481)) ([3cb34ff](https://github.com/SolaceLabs/solace-agent-mesh/commit/3cb34fff0e8377c5a8953ffb9f9b930cb1b80c30))
* **DATAGO-135912:** - gitpython vulnerabilities : solace-agent-mesh:main ([#1527](https://github.com/SolaceLabs/solace-agent-mesh/issues/1527)) ([06819b7](https://github.com/SolaceLabs/solace-agent-mesh/commit/06819b769aa5d3d50462d8997e968192d5a5fa15))
* **DATAGO-136560:** - [prod] investigatge solace-chat slowness ([#1533](https://github.com/SolaceLabs/solace-agent-mesh/issues/1533)) ([79387a4](https://github.com/SolaceLabs/solace-agent-mesh/commit/79387a440efbff5f2bfed1c51b080c77ccb83914))

## [1.25.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.24.1...1.25.0) (2026-05-11)


### Features

* **DATAGO-130042:** synthetic-monitor auth path for Datadog smoke tests ([#1461](https://github.com/SolaceLabs/solace-agent-mesh/issues/1461)) ([9a76c0f](https://github.com/SolaceLabs/solace-agent-mesh/commit/9a76c0f2abaa3dbeb37b1cfd1893b778e4abfe75))


### Bug Fixes

* **DATAGO-129192:** Fix broken link from a recent doc update ([#1511](https://github.com/SolaceLabs/solace-agent-mesh/issues/1511)) ([f9eac54](https://github.com/SolaceLabs/solace-agent-mesh/commit/f9eac54badbca691ec18f9b978b56753b218ad9a))
* **DATAGO-130050:** GH1258 Workflow nodes silently fail with "mandatory result embed" error if artifact_management tool group is missing  ([#1362](https://github.com/SolaceLabs/solace-agent-mesh/issues/1362)) ([7a7a2b8](https://github.com/SolaceLabs/solace-agent-mesh/commit/7a7a2b8b76b31f32c92d062bf609835b4c02039d))
* **DATAGO-134114:** replace hardcoded max_llm_calls_per_task with constant and increase value to 30 ([#1471](https://github.com/SolaceLabs/solace-agent-mesh/issues/1471)) ([5b94bee](https://github.com/SolaceLabs/solace-agent-mesh/commit/5b94bee0d47211bb2ff19d57f9c47fb4b5612efd))
* **DATAGO-134599:** Pre-filter empty sessions on /api/v1/artifacts/all ([#1491](https://github.com/SolaceLabs/solace-agent-mesh/issues/1491)) ([79f848e](https://github.com/SolaceLabs/solace-agent-mesh/commit/79f848e4cb4a797d71b5514283a697c405138b6a))
* **DATAGO-135081:** bump deps for critical/high vulnerability fixes ([#1509](https://github.com/SolaceLabs/solace-agent-mesh/issues/1509)) ([598d049](https://github.com/SolaceLabs/solace-agent-mesh/commit/598d0498ee7add44eac7542d736b36843fbb7d5e))
* **DATAGO-135081:** update libpng16 version to 1.6.48-1+deb13u5 in Dockerfile ([#1523](https://github.com/SolaceLabs/solace-agent-mesh/issues/1523)) ([6101c40](https://github.com/SolaceLabs/solace-agent-mesh/commit/6101c409931e30a5ff0b0414699ef940cbfc0cd7))


### Documentation

* **DATAGO-131495:** add Offline Evaluations UI documentation ([#1501](https://github.com/SolaceLabs/solace-agent-mesh/issues/1501)) ([4017879](https://github.com/SolaceLabs/solace-agent-mesh/commit/401787901812f774e9c20b95f898af17e991dd05))
* **DATAGO-131495:** fix broken links and leftover conflict marker in… ([#1514](https://github.com/SolaceLabs/solace-agent-mesh/issues/1514)) ([9b6a9c3](https://github.com/SolaceLabs/solace-agent-mesh/commit/9b6a9c31cb6e44135812ad01cc06c612c0c8bd23))
* **DATAGO-135351:** updating doctor docs ([#1515](https://github.com/SolaceLabs/solace-agent-mesh/issues/1515)) ([f53affd](https://github.com/SolaceLabs/solace-agent-mesh/commit/f53affd76cfff19eda98eca7da9d28360645d7e7))
* **DATAGO-135351:** updating error and log reference ([#1516](https://github.com/SolaceLabs/solace-agent-mesh/issues/1516)) ([a4804c2](https://github.com/SolaceLabs/solace-agent-mesh/commit/a4804c2ab628d1461870acf1c973f492825a7ef3))
* **DATAGO-135351:** updating sam-doctor docs for UX review ([#1522](https://github.com/SolaceLabs/solace-agent-mesh/issues/1522)) ([93267ef](https://github.com/SolaceLabs/solace-agent-mesh/commit/93267efc47125533f5303aa52baa54161e597bdf))

## [1.24.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.24.0...1.24.1) (2026-05-05)


### Bug Fixes

* **DATAGO-132447:** - Enable Support to Skip TLS verification for MCP tools/connectors ([#1495](https://github.com/SolaceLabs/solace-agent-mesh/issues/1495)) ([e2adc1e](https://github.com/SolaceLabs/solace-agent-mesh/commit/e2adc1ea2cba0e5a9d90495868110819c72efb58))

## [1.24.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.23.3...1.24.0) (2026-05-05)


### Features

* **DATAGO-134667:** promote offline_evals to beta and default true ([#1504](https://github.com/SolaceLabs/solace-agent-mesh/issues/1504)) ([d7050b0](https://github.com/SolaceLabs/solace-agent-mesh/commit/d7050b0cce143d80ac12e6b2b04cf1826a3e32f6))

## [1.23.3](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.23.2...1.23.3) (2026-05-05)


### Bug Fixes

* **DATAGO-134691:** improving artifacts appearing deleted during creation ([#1498](https://github.com/SolaceLabs/solace-agent-mesh/issues/1498)) ([ecfff47](https://github.com/SolaceLabs/solace-agent-mesh/commit/ecfff47fbb4dd215de75f8c6dc3d5c96808f0b2f))

## [1.23.2](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.23.1...1.23.2) (2026-05-05)


### Bug Fixes

* **DATAGO-134667:** strip max_input_tokens from per-request override ([#1499](https://github.com/SolaceLabs/solace-agent-mesh/issues/1499)) ([3f62e97](https://github.com/SolaceLabs/solace-agent-mesh/commit/3f62e975a7f780ebfebca2252c61a2131d930ca3))

## [1.23.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.23.0...1.23.1) (2026-05-04)


### Bug Fixes

* **agent:** lazy-init DynamicModelProvider for per-request model_override ([#1496](https://github.com/SolaceLabs/solace-agent-mesh/issues/1496)) ([371d6e9](https://github.com/SolaceLabs/solace-agent-mesh/commit/371d6e93581f1b5c602bc369a075614197a2b763))

## [1.23.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.22.1...1.23.0) (2026-04-30)


### Features

* **DATAGO-134503:** Experiment runs shows agent generated artifacts ([#1489](https://github.com/SolaceLabs/solace-agent-mesh/issues/1489)) ([496e671](https://github.com/SolaceLabs/solace-agent-mesh/commit/496e67196e4b7cc7b8008abecb87e828130d61ce))


### Bug Fixes

* **DATAGO-130894:** Update search input styling and positioning ([#1483](https://github.com/SolaceLabs/solace-agent-mesh/issues/1483)) ([53fd48f](https://github.com/SolaceLabs/solace-agent-mesh/commit/53fd48fad112a0c4806c7ec9e6949ec614dc5d91))


### Documentation

* **DATAGO-128303:** observability | documentation ([#1467](https://github.com/SolaceLabs/solace-agent-mesh/issues/1467)) ([31897dd](https://github.com/SolaceLabs/solace-agent-mesh/commit/31897dd2ed6872959cea6ebbe46970f27fe13259))

## [1.22.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.22.0...1.22.1) (2026-04-30)


### Bug Fixes

* **DATAGO-122712:** Enhance mention detection and add tests for multi-word queries ([#1484](https://github.com/SolaceLabs/solace-agent-mesh/issues/1484)) ([a02ef89](https://github.com/SolaceLabs/solace-agent-mesh/commit/a02ef890fdd68ef1a03f6b2daa8ec14f7ae505ff))
* **DATAGO-134531:** bump npm to 11.13.0 to fix brace-expansion CVE-&lt;&gt; ([#1487](https://github.com/SolaceLabs/solace-agent-mesh/issues/1487)) ([6478aea](https://github.com/SolaceLabs/solace-agent-mesh/commit/6478aea5834538d94515fdb15bdeea949f74deb1))

## [1.22.0](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.21.1...1.22.0) (2026-04-30)


### Features

* **DATAGO-133319:** Support attaching existing artifacts to chat messages ([#1429](https://github.com/SolaceLabs/solace-agent-mesh/issues/1429)) ([d84f8fb](https://github.com/SolaceLabs/solace-agent-mesh/commit/d84f8fb30479274895a54b84b83fd6f72c7065cb))

## [1.21.1](https://github.com/SolaceLabs/solace-agent-mesh/compare/1.21.0...1.21.1) (2026-04-29)


### Bug Fixes

* **DATAGO-134263:** honour per-node timeout in workflow agent calls ([#1476](https://github.com/SolaceLabs/solace-agent-mesh/issues/1476)) ([97dbb3f](https://github.com/SolaceLabs/solace-agent-mesh/commit/97dbb3f0d621aeb83fbf0f2f2f9c9642666cbc20))
* **DATAGO-134293:** Recent chats navigation randomly displays other users' chat history ([#1477](https://github.com/SolaceLabs/solace-agent-mesh/issues/1477)) ([aa9d6ad](https://github.com/SolaceLabs/solace-agent-mesh/commit/aa9d6ad27d9a849c2cac49126db9b7f765c15cd2))
* **DATAGO-134388:** Implement immediate UI feedback for sent prompts ([#1480](https://github.com/SolaceLabs/solace-agent-mesh/issues/1480)) ([cc348f0](https://github.com/SolaceLabs/solace-agent-mesh/commit/cc348f00ecf324c194ef7da4114ef771712f1c86))

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
