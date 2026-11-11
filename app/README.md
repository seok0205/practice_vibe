# app/ - 로또 6/45 즉석 추첨기 (Vibe Lotto 6/45) 아키텍처 및 개발 가이드라인

이 디렉토리(`app/`)는 **Phase 1(Kubernetes & CKA) ~ Phase 5(Terraform & AWS)** 전 과정에서 배포 및 고도화할 실습용 풀스택 웹 애플리케이션 **Vibe Lotto 6/45**의 소스 코드와 컨테이너 설정이 위치하는 공간입니다.

백엔드 엔지니어링 역량과 객체 지향 설계(OOP), 디자인 패턴을 극대화하기 위해 **FastAPI (Python)** 백엔드와 **Vite + React + TypeScript** 프론트엔드로 구성하며, 엄격한 코드 컨벤션과 다단계 코드 리뷰(2~3회 리팩터링) 및 자동화 테스트를 거쳐 완성합니다.

---

## 1. 서비스 기획 및 도메인 요구사항 (Domain Requirements)

### 1.1 핵심 게임 규칙 (6/45 로또 방식)
1. **번호 선택 범위**: `1 ~ 45`까지의 정수 중 중복 없이 **6개의 번호**를 선택합니다.
2. **추첨 방식 (즉석 대조)**:
   - 사용자가 **자동(Auto)**, **반자동(Semi-Auto: 일부 번호 선택 후 나머지 자동)**, 또는 **수동(Manual)**으로 6개 번호를 확정하고 추첨을 요청합니다.
   - 백엔드 시스템은 즉시 **당첨 번호 6개 + 보너스 번호 1개(총 7개)**를 난수로 추첨합니다.
   - 사용자의 선택 번호 6개와 시스템의 당첨 번호를 즉시 대조하여 등수를 판정합니다.
3. **당첨 등수 판정 기준**:
   - **1등 (`FIRST`)**: 당첨 번호 6개 모두 일치
   - **2등 (`SECOND`)**: 당첨 번호 5개 일치 + 보너스 번호 1개 일치
   - **3등 (`THIRD`)**: 당첨 번호 5개 일치 (보너스 번호 불일치)
   - **4등 (`FOURTH`)**: 당첨 번호 4개 일치
   - **5등 (`FIFTH`)**: 당첨 번호 3개 일치
   - **낙첨 (`MISS`)**: 당첨 번호 2개 이하 일치

### 1.2 사용자 경험(UX) 및 화면 레이아웃
- **좌측/중앙 메인 영역 (번호 선택 및 즉석 결과 보드)**:
  - `1 ~ 45` 번호판 그리드에서 직관적으로 번호를 토글 선택할 수 있습니다.
  - **UX 편의 기능 (반복 입력 피로도 제거)**:
    - **번호 유지(Keep / Lock) 토글**: 추첨이 끝난 후에도 현재 선택한 번호를 초기화하지 않고 그대로 유지하여 연속 추첨을 바로 누를 수 있는 모드입니다.
    - **고정수(Pin) 지정**: 특정 번호 몇 개만 고정(Pin)해 두고 나머지 번호만 자동으로 채우는 반자동 기능입니다.
    - **이전 번호 불러오기(Load Previous)**: 직전 회차들에 선택했던 번호 조합을 원클릭으로 다시 불러옵니다.
- **우측 사이드 영역 (명예의 전당 - 5등 이상 당첨 기록)**:
  - 추첨 결과 중 **5등(`FIFTH`) 이상 당첨된 이력만 필터링하여 우측 타임라인에 영구 기록**합니다.
  - 각 기록 카드에는 회차(또는 시간), 당첨 등수 배지, 내가 선택한 번호(일치 번호 하이라이트), 시스템 당첨 번호 + 보너스 번호, 그리고 **해당 요청을 처리한 Kubernetes Pod 이름(`hostname`)**이 함께 표시됩니다.

### 1.3 Kubernetes & DevOps 실습 연동 기능
단순한 웹 앱을 넘어 K8s 클러스터 기능을 시각적으로 검증하기 위해 아래 엔드포인트와 메타데이터를 기본 제공합니다:
- **Pod 식별자 노출**: 모든 API 응답 헤더와 UI 하단 상태바에 현재 응답을 처리한 파드의 `HOSTNAME`(Pod Name), 앱 버전(`APP_VERSION`), 환경(`APP_ENV`)을 표시하여 `Service` 로드밸런싱 및 `RollingUpdate`를 실시간으로 눈으로 확인합니다.
- **헬스체크 API (`/api/v1/health/live`, `/api/v1/health/ready`)**: K8s `livenessProbe`, `readinessProbe`, `startupProbe` 실습을 위한 상태 검사 및 의도적 장애 시뮬레이션 기능을 제공합니다.
- **영구 스토리지 및 데이터베이스 연동 (`MySQL` + `PV/PVC`)**:
  - 5등 이상 당첨 기록을 저장하기 위해 관계형 데이터베이스인 **MySQL**(`lotto_winning_records` 테이블)을 기본 영속성 저장소로 연동합니다.
  - 이를 통해 Kubernetes 실습에서 **StatefulSet(또는 MySQL Deployment + PVC)**, **Secret(DB 비밀번호 주입)**, **Service(클러스터 내부 DNS `mysql-service:3306` 통신)**, **InitContainer(DB 기동 대기)**를 완벽하게 실습할 수 있습니다.
  - 로그인/회원가입 등 세션 관리가 없으므로 Redis 등 별도 캐시 서버는 두지 않고 아키텍처를 담백하게 유지합니다.

---

## 2. 데이터베이스 스키마 및 시스템 아키텍처 (DB Schema & OOP Design Patterns)

### 2.1 MySQL 테이블 스키마 (`lotto_winning_records`)
5등 이상 당첨된 이력만 저장하며, 복잡한 조인이나 대규모 범위 검색이 없고 최신 당첨 내역 조회(`ORDER BY id DESC LIMIT N`)가 주된 쿼리이므로 **Primary Key(`id`) 클러스터드 인덱스 외에 별도의 보조 인덱스(Secondary Index)는 생성하지 않아 쓰기(INSERT) 성능과 단순성을 유지**합니다.

| 컬럼명 (Column) | 데이터 타입 (Type) | 제약 조건 (Constraints) | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY, AUTO_INCREMENT` | 당첨 기록 고유 식별자 (기본 Clustered Index로 최신순 정렬에 활용) |
| `first_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 1번째 번호 (오름차순 정렬 기준) |
| `second_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 2번째 번호 |
| `third_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 3번째 번호 |
| `fourth_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 4번째 번호 |
| `fifth_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 5번째 번호 |
| `sixth_num` | `TINYINT UNSIGNED` | `NOT NULL` (1~45) | 사용자가 선택한 6번째 번호 |
| `winning_rank` | `TINYINT UNSIGNED` | `NOT NULL` (1~5) | 당첨 등수 (`1`: 1등 ~ `5`: 5등, SQL 예약어 `RANK()`와의 충돌 방지를 위해 컬럼명은 `winning_rank` 또는 백틱 `` `rank` `` 처리) |
| `created_at` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | 당첨 시각 |

> **참고**: MySQL 8.0+에서 `RANK`는 윈도우 함수 예약어(Reserved Word)이므로, ORM(SQLAlchemy) 및 순수 SQL에서 문법 에러를 방지하기 위해 물리 컬럼 또는 매핑 시 안전하게 다루도록 설계합니다.

### 2.2 계층형 아키텍처 및 디자인 패턴 (Layered Architecture & DDD)

백엔드 엔지니어의 관점에서 확장성과 테스트 용이성(Testability)을 확보하기 위해 **계층형 아키텍처 + 도메인 주도 설계(DDD) 전술적 패턴**을 적용합니다.

```mermaid
flowchart TB
    subgraph Frontend["Frontend (Vite + React + TypeScript)"]
        UI["UI Components\n(Board, ResultView, WinningHistorySidebar)"]
        Hook["Custom Hooks & State Facade\n(useLottoGame)"]
        APIClient["Typed API Client Service\n(LottoApiClient)"]
        UI --> Hook --> APIClient
    end

    subgraph Backend["Backend (FastAPI + Python OOP)"]
        Router["Presentation Layer (FastAPI Routers / DTOs)"]
        Service["Application Layer (LottoGameService / Facade)"]
        subgraph Domain["Domain Layer (Pure OOP & Design Patterns)"]
            VO["Value Objects\n(LottoNumber, LottoTicket, WinningDraw)"]
            Strategy["NumberGeneratorStrategy\n(Auto / SemiAuto / Manual)"]
            Chain["RankEvaluatorPolicy\n(1등 ~ 5등 / 낙첨 판정)"]
            Factory["LottoTicketFactory"]
        end
        subgraph Infra["Infrastructure Layer (Repository Pattern)"]
            RepoInterface["WinningRecordRepository (ABC)"]
            MySQLRepo["MySQLWinningRepository (SQLAlchemy + PyMySQL)"]
            MemRepo["InMemoryWinningRepository (Test / Local Fallback)"]
        end

        Router -->|Dependency Injection| Service
        Service --> VO
        Service --> Strategy
        Service --> Chain
        Service --> RepoInterface
        RepoInterface <|.. MySQLRepo
        RepoInterface <|.. MemRepo
    end

    MySQL[("MySQL 8.0 DB\n(lotto_winning_records)")]
    APIClient -->|HTTP REST JSON| Router
    MySQLRepo -->|TCP 3306| MySQL
```

### 2.1 적용할 핵심 디자인 패턴 (Design Patterns)
1. **Value Object (값 객체 패턴) & 일급 컬렉션 (First-Class Collection)**:
   - 번호 하나를 단순 `int`로 다루지 않고 불변(Immutable) 객체인 `LottoNumber`로 캡슐화하여 `1 <= n <= 45` 범위 검증을 객체 생성 시점에 강제합니다.
   - 6개의 번호 묶음을 `LottoTicket` 일급 컬렉션으로 정의하여 중복 방지, 오름차순 정렬, 고정수 병합, 당첨 번호와의 교집합 연산(`match_count`) 등 비즈니스 로직을 데이터와 한곳에 응집시킵니다.
2. **Strategy Pattern (전략 패턴 - 번호 생성 및 등수 판정)**:
   - `NumberGenerationStrategy` 추상 인터페이스(ABC)를 정의하고, `AutoGenerationStrategy`(완전 자동), `SemiAutoGenerationStrategy`(고정수 유지 + 나머지 자동), `ManualGenerationStrategy`(수동 검증)를 다형성(Polymorphism)으로 교체 가능하게 설계합니다.
   - `RankEvaluationPolicy`를 통해 일치 개수 및 보너스 번호 일치 여부에 따른 등수 판정 알고리즘을 캡슐화합니다.
3. **Repository Pattern (저장소 패턴) & Dependency Injection (의존성 주입)**:
   - 5등 이상 당첨 기록을 저장하는 `WinningHistoryRepository` 추상 클래스(인터페이스)를 두어, 도메인/서비스 계층이 구체적인 저장 매체(MySQL인지, 인메모리인지)를 전혀 몰라도 되도록 의존성을 역전(DIP)시킵니다.
   - FastAPI의 `Depends`와 설정(`ConfigMap` 및 `Secret` 환경변수 `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)을 통해 런타임에 `MySQLWinningRepository` 또는 테스트용 `InMemoryWinningRepository`를 주입합니다.
4. **Factory Pattern (팩토리 패턴)**:
   - 클라이언트 요청 모드(`AUTO`, `SEMI_AUTO`, `MANUAL`)에 알맞은 번호 생성 전략과 티켓 객체를 조립해 주는 `LottoTicketFactory`를 구현합니다.

---

## 3. 코드 컨벤션 (Coding Conventions)

### 3.1 Python (FastAPI Backend) 컨벤션
1. **스타일 및 포매팅**:
   - **PEP 8** 표준을 엄격히 준수하며, 라인 길이는 최대 `100`자로 제한합니다.
   - 네이밍 규칙: 클래스명은 `PascalCase`, 함수/메서드/변수명은 `snake_case`, 상수는 `UPPER_SNAKE_CASE`, 비공개(Private/Protected) 속성은 `_leading_underscore`를 사용합니다.
2. **엄격한 타입 힌팅 (Strict Type Hints)**:
   - 모든 함수와 메서드의 매개변수 및 반환값에 Python 3.10+ 표준 타입 힌트(`list[int]`, `int | None`, `Self` 등)를 100% 명시합니다. `Any` 타입 사용을 금지합니다.
3. **객체 지향 설계(SOLID) 및 불변성(Immutability)**:
   - 도메인 값 객체(Value Object)는 `@dataclass(frozen=True, slots=True)`를 사용하여 불변성과 메모리 효율성을 보장합니다.
   - **Tell, Don't Ask 원칙**: 객체의 데이터를 꺼내서(`getter`) 외부 절차적 코드에서 판단하지 말고, 객체에게 메시지를 보내 스스로 판단하게 합니다(예: `winning_draw.evaluate(user_ticket)`).
   - 추상 계층은 `abc.ABC`와 `@abstractmethod` 또는 `typing.Protocol`을 명확히 사용합니다.
4. **예외 처리 및 API 스키마**:
   - 도메인 규칙 위반 시 내장 `ValueError`를 그대로 노출하지 않고, `DomainError`(`InvalidLottoNumberError`, `DuplicateNumberError` 등) 커스텀 예외 계층을 정의한 뒤 FastAPI Global Exception Handler에서 표준화된 HTTP 응답(RFC 7807 Problem Details 형태)으로 변환합니다.
   - API 입출력 DTO는 `Pydantic v2`(`BaseModel`, `ConfigDict`, `Field`)를 사용하며, 도메인 엔티티와 API DTO를 철저히 분리합니다.

### 3.2 TypeScript (React Frontend) 컨벤션
1. **TypeScript 컴파일러 엄격 모드 (`strict: true`)**:
   - `any` 타입 사용을 절대 금지하며, 알 수 없는 외부 데이터는 `unknown`으로 받은 뒤 Type Guard로 좁혀서 사용합니다.
   - 상태나 결과를 표현할 때는 **Discriminated Union(구별된 유니온)** 타입과 `readonly` 속성(`readonly number[]`)을 적극 활용하여 불변성을 유지합니다.
2. **네이밍 및 파일 구조**:
   - 컴포넌트 및 클래스: `PascalCase` (예: `LottoBoard.tsx`, `LottoApiClient.ts`)
   - 커스텀 훅: `use` 접두사를 포함한 `camelCase` (예: `useLottoGame.ts`)
   - 상수 및 열거형 객체: `as const`를 활용한 상수 객체 패턴 권장 (`LottoRank`)
3. **관심사 분리 (Separation of Concerns)**:
   - **UI 컴포넌트(Presentational)**는 화면 렌더링과 이벤트 전달에만 집중하며, 직접 `fetch`를 호출하거나 복잡한 비즈니스 계산을 수행하지 않습니다.
   - 번호 선택/유지(Keep)/고정(Pin)/이전 번호 복원 같은 클라이언트 상태 제어는 도메인 모델 클래스 또는 전용 Custom Hook(`useLottoTicketState`)으로 캡슐화합니다.
   - 백엔드 통신은 캡슐화된 클래스(`LottoApiClient`)를 통해 수행하며 에러 핸들링과 타임아웃을 일관되게 처리합니다.

---

## 4. 코드 리뷰 및 리팩터링 가이드라인 (Multi-Pass Code Review Process)

코드를 최초 작성한 후 바로 완료 처리하지 않고, 아래 **3단계 리뷰 체크리스트**에 따라 **최소 2~3회의 자체 코드 리뷰 및 리팩터링 사이클**을 수행하고 그 이력을 문서화합니다.

### Pass 1: 객체 지향 설계(OOP) 및 디자인 패턴 적합성 리뷰
- [ ] **단일 책임 원칙(SRP)**: 특정 클래스나 함수가 두 가지 이상의 변경 이유를 가지고 있지 않은가? (예: 추첨 로직과 파일 저장 로직이 섞여 있지 않은가?)
- [ ] **개방-폐쇄 원칙(OCP)**: 새로운 번호 생성 방식이나 저장소(예: Redis)가 추가될 때 기존 서비스 코드를 수정하지 않고 확장할 수 있는가?
- [ ] **캡슐화 및 불변성**: 외부에서 일급 컬렉션(`LottoTicket`) 내부의 리스트를 직접 조작(`append`, `pop`)할 수 있는 구멍이 남아 있지 않은가?
- [ ] **도메인 순수성**: Domain 계층이 FastAPI나 파일시스템(IO) 라이브러리에 의존하고 있지 않은가?

### Pass 2: 클린 코드, 타입 안정성 및 엣지 케이스(Edge Cases) 리뷰
- [ ] **유효성 검증**: 수동/반자동 선택 시 범위를 벗어난 숫자(`0`, `46`), 중복된 숫자, 개수가 부족하거나 넘치는 입력에 대해 백엔드와 프론트엔드 양쪽에서 방어하고 있는가?
- [ ] **동시성 및 I/O 안전성**: 5등 이상 기록을 파일(`PVC`)에 저장할 때 파일이 없거나 손상된 경우, 또는 동시에 요청이 들어올 때 안전하게 처리(Lock 또는 원자적 쓰기)되는가?
- [ ] **UX 디테일**: '번호 유지(Keep)'나 '이전 번호 불러오기' 클릭 시 고정수(Pin) 상태와 충돌하지 않고 매끄럽게 동작하는가?

### Pass 3: 테스트 커버리지 및 Kubernetes/컨테이너 최적화 리뷰
- [ ] **백엔드 단위/통합 테스트 (`pytest`)**:
  - 1등 ~ 5등, 낙첨 판정 경계값 테스트가 모두 작성되었는가? (특히 2등 '5개+보너스'와 3등 '5개 일치'의 정확한 구분)
  - 전략 패턴별(자동/반자동/수동) 번호 생성 테스트 및 예외 발생 테스트가 통과하는가?
  - API 엔드포인트(`POST /api/v1/lotto/draw`, `GET /api/v1/lotto/history`, `/api/v1/health/*`) 통합 테스트가 통과하는가?
- [ ] **프론트엔드 검증 (`tsc` & `vitest` / `build`)**:
  - TypeScript 타입 체크(`tsc --noEmit`) 및 프로덕션 번들 빌드(`vite build`)가 경고/에러 없이 통과하는가?
- [ ] **컨테이너 및 주석 규칙(`AGENTS.md`)**:
  - 멀티 스테이지 `Dockerfile`이 non-root 유저로 실행되며 이미지 크기가 최적화되었는가?
  - 모든 파일에 학습을 위한 상세한 아키텍처/패턴/필드 설명 주석이 한국어로 누락 없이 작성되었는가?

---

## 5. 디렉토리 구조 (Directory Layout)

```text
app/
├── README.md                        # 앱 아키텍처, OOP 패턴, 코드 컨벤션, 리뷰 가이드라인 (현재 문서)
├── CODE_REVIEW_LOG.md               # 3회에 걸친 코드 리뷰 및 리팩터링 전/후 비교 기록 문서
├── docker-compose.yml               # 로컬 개발용 통합 실행 환경 (App + MySQL 8.0)
├── Dockerfile                       # Frontend 빌드 + Backend 실행을 통합한 Multi-stage Dockerfile
├── backend/                         # FastAPI 백엔드 (Python)
│   ├── pyproject.toml               # 의존성(SQLAlchemy, PyMySQL 포함) 및 pytest, ruff, mypy 설정
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 엔트리포인트 및 DI 컨테이너 조립
│   │   ├── core/                    # 환경설정(Config - MySQL 접속 정보 포함), 예외 클래스
│   │   ├── domain/                  # 순수 OOP 도메인 모델 (Value Objects, Strategies, Evaluator, Repository ABC)
│   │   ├── application/             # 유스케이스 서비스 및 Facade (LottoGameService)
│   │   ├── infrastructure/          # MySQLWinningRepository (SQLAlchemy ORM) 및 InMemoryWinningRepository
│   │   └── presentation/            # REST API 라우터 및 Pydantic Request/Response DTO
│   └── tests/                       # 단위 테스트(Domain/Strategy) 및 API 통합 테스트
└── frontend/                        # React + TypeScript 프론트엔드 (Vite)
    ├── package.json
    ├── tsconfig.json                # strict: true 설정
    └── src/
        ├── domain/                  # 프론트엔드 도메인 타입 및 티켓 상태 관리 모델
        ├── services/                # LottoApiClient (백엔드 통신 캡슐화)
        ├── hooks/                   # useLottoGame (번호 유지, 이전 번호, 추첨 상태 관리 훅)
        └── components/              # LottoBoard, ControlPanel, DrawResultModal, WinningHistorySidebar
```
