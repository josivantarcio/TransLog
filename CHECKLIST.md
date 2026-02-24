# TransLog Backend — Checklist de Implementação

> Última atualização: 2026-02-24
> Testes: **161 passando** | Cobertura: ~75%

---

## ⚠️ Revisão Pendente (próxima sessão)

**Análise de complexidade Big-O** — antes de continuar novas features, revisar:
- Queries sem índice adequado (N+1, full table scan)
- Paginação: verificar se `COUNT(*)` sobre subquery é O(n) e se pode ser otimizado
- `get_history` do tracking: limite de 200 registros — avaliar se precisa de cursor-based pagination
- Listagens com filtros: verificar planos de execução (EXPLAIN ANALYZE) nas queries principais
- Redis: avaliar se as chaves têm TTL adequado e se o padrão de acesso é O(1)
- Haversine no `confirm_delivery`: O(1) — ok, mas verificar se GPS validation pode ser indexada futuramente

---

## Legenda
- ✅ Feito e com testes
- 🔄 Em andamento
- ⬜ Pendente

---

## P1 — Autenticação (issue #1 encerrado indiretamente)
- ✅ POST `/auth/login` — login multi-tenant, retorna access + refresh token
- ✅ POST `/auth/refresh` — renova access token via refresh token
- ✅ POST `/auth/logout` — invalida refresh token no Redis (blacklist)
- ✅ GET `/auth/me` — retorna dados do usuário autenticado
- ✅ Verificação de email (token por link)
- ✅ JWT carrega `tenant_id` + `role` (sem roundtrip ao banco por request)

## P2 — Tenants e Usuários
- ✅ **Issue #1** POST `/tenants/onboard` — cria tenant + admin inicial
- ✅ GET/PATCH `/tenants/me` — dados do tenant autenticado
- ✅ GET `/tenants/{id}`, suspend, activate, list (admin global)
- ✅ **Issue #2** CRUD completo de Usuários (`/users`)
- ✅ POST `/users/{id}/change-password` — troca senha autenticado
- ✅ POST `/users/{id}/reset-password` — reset de senha (admin)
- ✅ Proteção: não é possível desativar o último admin do tenant

## P3 — Veículos, Entregas e Documentos
- ✅ **Issue #3** CRUD completo de Veículos (`/vehicles`)
- ✅ **Issue #4** CRUD de Entregas (`/deliveries`) com paginação e filtros
- ✅ **Issue #5** Fluxo de conclusão de entrega:
  - POST `/{id}/assign` — atribui motorista e veículo (PENDING → IN_TRANSIT)
  - POST `/{id}/initiate-completion` — motorista escaneia QR, gera OTP TOTP, envia por email
  - POST `/{id}/confirm` — valida OTP + GPS → DELIVERED
  - POST `/{id}/authorize-operator` — fallback: operador usa OTP do cliente
  - POST `/{id}/authorize-admin` — fallback: admin usa própria senha
  - POST `/{id}/cancel` — cancela entrega
  - GET `/{id}/qrcode` — retorna QR Code em base64
- ✅ **Issue #15** GET `/{id}/receipt` — comprovante de entrega em PDF (apenas DELIVERED)
- ⬜ **Issue #12** Notificações por Email: templates HTML e fila de envio

## P4 — Rastreamento e Documentos Operacionais
- ✅ **Issue #6** Rastreamento GPS em tempo real:
  - POST `/tracking/` — motorista envia posição (salvo Postgres + Redis + pub/sub)
  - GET `/tracking/{id}/live` — posição ao vivo via Redis
  - GET `/tracking/{id}` — histórico de eventos GPS (Postgres)
  - WS `ws://…/ws/tracking/{id}` — WebSocket para updates em tempo real
- ⬜ **Issue #13** Romaneio de Entrega — PDF com lista de volumes por motorista/rota
- ⬜ **Issue #14** Espelho de Carga — PDF com agrupamento por veículo/data
- ⬜ **Issue #11** Dashboard e Relatórios por Tenant
- ⬜ **Issue #16** Relatórios Operacionais: entregas, motoristas, ocorrências, CSV

## P5 — Pagamentos
- ⬜ **Issue #7** Integração Asaas:
  - Criar customer Asaas no onboard do tenant
  - Webhook para ativar/suspender tenant conforme pagamento

## P6 — Infraestrutura e Segurança
- ⬜ **Issue #8** Middleware: Rate Limiting, verificação de status do Tenant, Request ID
- ⬜ **Issue #9** CI/CD: GitHub Actions + relatório de cobertura de testes
- ⬜ **Issue #10** Segurança adicional: logout de todos os devices, proteção de endpoints

---

## Endpoints disponíveis (resumo)

| Método | Endpoint | Roles | Status |
|--------|----------|-------|--------|
| POST | `/api/v1/auth/login` | público | ✅ |
| POST | `/api/v1/auth/refresh` | público | ✅ |
| POST | `/api/v1/auth/logout` | autenticado | ✅ |
| GET | `/api/v1/auth/me` | autenticado | ✅ |
| POST | `/api/v1/tenants/onboard` | público | ✅ |
| GET/PATCH | `/api/v1/tenants/me` | admin | ✅ |
| POST | `/api/v1/users/` | admin | ✅ |
| GET/PATCH/DELETE | `/api/v1/users/{id}` | admin | ✅ |
| POST | `/api/v1/vehicles/` | admin | ✅ |
| GET | `/api/v1/vehicles/` | admin, driver | ✅ |
| POST | `/api/v1/deliveries/` | admin | ✅ |
| GET | `/api/v1/deliveries/` | admin, driver | ✅ |
| GET | `/api/v1/deliveries/{id}` | admin, driver | ✅ |
| POST | `/api/v1/deliveries/{id}/assign` | admin | ✅ |
| POST | `/api/v1/deliveries/{id}/initiate-completion` | driver | ✅ |
| POST | `/api/v1/deliveries/{id}/confirm` | driver | ✅ |
| POST | `/api/v1/deliveries/{id}/authorize-operator` | admin, driver | ✅ |
| POST | `/api/v1/deliveries/{id}/authorize-admin` | admin | ✅ |
| POST | `/api/v1/deliveries/{id}/cancel` | admin | ✅ |
| GET | `/api/v1/deliveries/{id}/qrcode` | admin, driver | ✅ |
| GET | `/api/v1/deliveries/{id}/receipt` | admin, driver | ✅ |
| POST | `/api/v1/tracking/` | driver | ✅ |
| GET | `/api/v1/tracking/{id}/live` | admin, driver | ✅ |
| GET | `/api/v1/tracking/{id}` | admin, driver | ✅ |
| WS | `/ws/tracking/{id}` | — | ✅ |
| GET | `/health` | público | ✅ |
