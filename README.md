# service-delivery-record

이 repo는 배송 원천 기록 정본과 일별 집계 입력 정본을 제공하는 active runtime repo다.

현재 역할:
- `delivery-record-api` runtime
- 배송 원천 기록 API
- 일별 집계 입력 snapshot API
- authenticated read / admin write gate

이 repo는 절대 소유하지 않음:
- `SettlementRun`
- `SettlementItem`
- payout/result truth
- settlement read-model API

현재 소유 범위:
- 배송원 원천 기록 정본
- 정산 전 집계 입력용 일별 snapshot 정본

포함 범위:
- runtime code
- DB migration
- API
- seed 대상 데이터

현재 정본:
- `../../docs/mappings/`

이력 / 컨텍스트:
- `../../docs/archive/historical/rollout/2026-03-20-settlement-phase-1-decomposition-implementation-plan.md`
