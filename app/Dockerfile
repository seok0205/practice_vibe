# ==============================================================================
# [파일 목적]
# Vibe Lotto 6/45 풀스택 애플리케이션(React+TS 프론트엔드 + FastAPI 백엔드)을
# 단일 경량 컨테이너 이미지로 패키징하는 Multi-Stage Dockerfile입니다.
#
# [보안 및 컨테이너 최적화 포인트 (CKA / DevSecOps 모범 사례)]
# 1. Multi-stage Build:
#    - Stage 1(`frontend-builder`)에서 Node.js로 TypeScript 타입 검사(`tsc -b`) 및
#      프로덕션 정적 번들(`dist/`)을 빌드한 뒤, 최종 이미지에는 Node.js 런타임과 `node_modules`를
#      포함하지 않아 이미지 용량과 공격 표면(Attack Surface)을 대폭 줄입니다.
# 2. Layer Caching 최적화:
#    - 소스 코드보다 변경 빈도가 낮은 `package.json`과 `requirements.txt`를 먼저 복사하여
#      의존성 설치 레이어가 캐싱되도록 설계했습니다.
# 3. Non-root User 실행 (`SecurityContext` 호환):
#    - 컨테이너가 `root`(UID 0)로 실행되어 호스트 커널 권한 탈취에 악용되는 것을 막기 위해
#      UID `10001`을 가진 비특권 유저(`appuser`)를 생성하여 프로세스를 구동합니다.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend Builder (Node.js 20 Alpine)
# 역할: TypeScript 컴파일 체크 및 React 정적 에셋(`dist/`) 생성
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# 의존성 정의 파일만 먼저 복사하여 npm install 레이어 캐싱 극대화
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

# 프론트엔드 전체 소스 복사 후 TypeScript 엄격 타입 검사 및 Vite 번들링 실행
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Backend & Runtime Image (Python 3.12 Slim)
# 역할: FastAPI 백엔드 구동 및 Stage 1에서 빌드된 정적 웹 에셋 서빙
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# 파이썬 바이트코드(.pyc) 생성 방지 및 표준 출력 버퍼링 비활성화(K8s `kubectl logs` 실시간 출력용)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_NAME="Vibe Lotto 6/45" \
    APP_VERSION="1.0.0" \
    APP_ENV="prod" \
    LOTTO_STORAGE_BACKEND="mysql" \
    LOTTO_STATIC_DIR="/app/static"

WORKDIR /app

# 비루트(Non-root) 시스템 그룹 및 유저(UID 10001) 생성
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /sbin/nologin --create-home appuser

# Python 의존성 설치 (캐시 디렉토리 미사용으로 이미지 용량 절감)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 백엔드 애플리케이션 코드 복사
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/pyproject.toml ./

# Stage 1에서 빌드된 React 정적 파일을 `/app/static` 경로로 복사
COPY --from=frontend-builder /build/frontend/dist /app/static

# 소유권을 비특권 유저(appuser)로 변경 후 유저 전환
RUN chown -R appuser:appgroup /app
USER 10001:10001

# 컨테이너 수신 포트 명시 (K8s containerPort: 8000과 매핑)
EXPOSE 8000

# Uvicorn ASGI 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

