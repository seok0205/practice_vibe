# Vibe Lotto 6/45 다단계 코드 리뷰 및 리팩터링 기록 (Code Review Log)

이 문서는 [`app/README.md`](./README.md)의 **4. 코드 리뷰 및 리팩터링 가이드라인**에 따라 최초 구현된 백엔드(FastAPI + SQLAlchemy MySQL) 및 프론트엔드(React + TypeScript) 코드를 대상으로 **총 3회(Pass 1 ~ Pass 3)에 걸쳐 수행한 자체 코드 리뷰와 리팩터링 내역**을 기록합니다.

---

## Pass 1: 객체 지향 설계(OOP) 및 디자인 패턴 적합성 리뷰

### 1.1 [리뷰 지적] `RankEvaluationPolicy`의 Feature Envy (Tell, Don't Ask 위반)
- **문제점 (Before)**:
  `RankEvaluationPolicy.evaluate()` 메서드가 `winning_draw.main_ticket`과 `winning_draw.bonus_number` 속성을 외부에서 각각 꺼내어(`getter`) `user_ticket`과 비교 연산을 수행하고 있었습니다. 이는 객체의 내부 데이터를 꺼내 절차적으로 처리하는 전형적인 Feature Envy 안티패턴이었습니다.
- **리팩터링 (After)**:
  [`app/backend/app/domain/models.py`](./backend/app/domain/models.py)의 `WinningDraw` 도메인 객체에 `match_against(user_ticket)` 메서드를 추가하여, 당첨 번호 객체 스스로 일치 번호 튜플과 보너스 번호 일치 여부를 계산해 반환하도록 **Tell, Don't Ask 원칙**을 적용했습니다.

### 1.2 [리뷰 지적] `WinningRecordEntity`의 도메인 불변식(Invariant) 보호 부족
- **문제점 (Before)**:
  "5등 이상 당첨된 결과만 우측 명예의 전당 및 MySQL DB에 기록한다"는 핵심 비즈니스 규칙이 `LottoGameService.play_round()`의 `if result.is_winning_tier:` 조건문에만 의존하고 있었고, 정작 `WinningRecordEntity.create_new()`는 낙첨(`LottoRank.MISS`)이 전달되어도 엔티티 생성을 허용했습니다.
- **리팩터링 (After)**:
  [`WinningRecordEntity.create_new()`](./backend/app/domain/models.py) 내부에서 `if not rank.is_winning:` 검사를 수행하여 낙첨 등급으로 엔티티 생성을 시도하면 즉시 `LottoDomainError(error_code="NON_WINNING_RECORD_NOT_ALLOWED")`를 던지도록 방어 로직을 도메인 계층에 응집시켰습니다.

### 1.3 [리뷰 지적] `TicketGenerationStrategyFactory`의 개방-폐쇄 원칙(OCP) 확장성
- **문제점 (Before)**:
  팩토리 생성자 내부에 3가지 기본 전략(`AUTO`, `SEMI_AUTO`, `MANUAL`)이 하드코딩되어 있어 새로운 전략(예: 홀짝 균형 전략 등)을 외부에서 주입하거나 등록할 수 없었습니다.
- **리팩터링 (After)**:
  [`TicketGenerationStrategyFactory`](./backend/app/domain/strategies.py) 생성자가 `custom_strategies: Iterable[NumberGenerationStrategy] | None`을 주입받을 수 있게 개선하고, `register_strategy()` 메서드를 추가하여 기존 팩토리 코드를 수정하지 않고도 전략을 확장할 수 있게 리팩터링했습니다.

---

## Pass 2: 클린 코드, MySQL 연동 안정성 및 UX 엣지 케이스 리뷰

### 2.1 [리뷰 지적] SQLAlchemy 1.x 레거시 쿼리 문법 및 MySQL 기동 순서(Race Condition) 방어
- **문제점 (Before)**:
  1. `MySQLWinningRepository.clear_all()`에서 SQLAlchemy 1.x 스타일인 `session.query(WinningRecordORM).delete()`를 사용하고 있었습니다.
  2. Kubernetes 환경에서 백엔드 파드와 MySQL 파드가 동시에 뜰 때, 백엔드의 `lifespan` 시점에는 MySQL이 아직 준비되지 않아 `init_schema()`가 스킵되면 이후 MySQL이 정상 기동되어도 테이블(`lotto_winning_records`)이 생성되지 않은 채로 남는 엣지 케이스가 있었습니다.
- **리팩터링 (After)**:
  1. [`MySQLWinningRepository.clear_all()`](./backend/app/infrastructure/mysql_repository.py)을 SQLAlchemy 2.0 표준인 `delete(WinningRecordORM)` + `session.execute(stmt)` 구문으로 전면 교체했습니다.
  2. `_schema_ready` 플래그를 도입하여 초기 기동 시 스키마 생성이 지연되었더라도 이후 첫 DB 작업(`save`, `find_recent`, `count_all`) 시점에 멱등성 있게 `init_schema()`(`CREATE TABLE IF NOT EXISTS`)를 자동 수행하도록 **Self-Healing** 로직을 보강했습니다.

### 2.2 [리뷰 지적] 프론트엔드 '이전 번호 불러오기' 시 고정수(Pin)와의 충돌 버그
- **문제점 (Before)**:
  사용자가 특정 번호 2개(예: `10, 20`)를 고정수(Pin)로 설정한 상태에서, '최근 번호 불러오기' 또는 '명예의 전당 이 번호 쓰기'로 `[1, 2, 3, 4, 5, 6]`을 불러오면 기존 고정수 상태가 그대로 남아 의도치 않은 동작을 유발할 수 있었습니다.
- **리팩터링 (After)**:
  [`TicketSelectionModel.restoreNumbers()`](./frontend/src/domain/lotto.ts)에서 복원하려는 6개 번호를 온전히 선택 상태에 담고, 기존 고정수 중 복원 번호에 포함되는 번호만 교집합으로 핀을 유지하도록 수정했습니다.

### 2.3 [리뷰 지적] `LottoApiClient` 네트워크 타임아웃 제어 부재
- **문제점 (Before)**:
  백엔드 파드나 MySQL 연결이 행(Hang) 상태에 빠졌을 때 프론트엔드 `fetch`가 무한 대기하는 문제가 있었습니다.
- **리팩터링 (After)**:
  [`LottoApiClient.request()`](./frontend/src/services/LottoApiClient.ts)에 `AbortController` 기반 타임아웃(기본 8초)을 추가하여, 지연 발생 시 명확한 한국어 안내 메시지와 함께 요청을 안전하게 중단하도록 개선했습니다.

---

## Pass 3: 테스트 커버리지, PEP 8 컨벤션 및 컨테이너 보안 리뷰

### 3.1 PEP 8 줄 길이(100자) 및 타입 안정성 점검
- 모든 Python 파일에서 100자를 초과하는 라인을 여러 줄로 정렬하고, `from __future__ import annotations`와 엄격한 타입 힌트를 적용했습니다.
- 파이썬에서 `isinstance(True, int)`가 `True`로 평가되는 함정을 [`LottoNumber.__post_init__`](./backend/app/domain/models.py)에서 명시적으로 차단하고 이를 단위 테스트(`test_boolean_rejected_even_though_subclass_of_int`)로 검증했습니다.

### 3.2 테스트 스위트 구축 완료
- [`tests/test_domain.py`](./backend/tests/test_domain.py): 값 객체 범위 검증, 일급 컬렉션 정렬/중복 차단, 1등~5등 및 낙첨(특히 2개+보너스 일치 시 낙첨 처리, 5개+보너스 2등 vs 5개 3등 구분) 경계값 테스트, 자동/반자동/수동 전략 테스트 작성
- [`tests/test_api_and_repository.py`](./backend/tests/test_api_and_repository.py): SQLAlchemy `MySQLWinningRepository` CRUD 및 `lotto_winning_records` 테이블(`id`, `first_num`~`sixth_num`, `rank`) 검증, FastAPI 엔드포인트 통합 테스트 및 K8s Probe(`/api/v1/health/live`, `/api/v1/health/ready`) 검증 완료

