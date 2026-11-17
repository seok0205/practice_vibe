# 01. Kubernetes 핵심 마스터 및 CKA 자격증 취득 커리큘럼

> **학습 목표**: 샘플 애플리케이션을 Kubernetes 클러스터에 안정적으로 배포하고, **CKA(Certified Kubernetes Administrator)** 시험의 5대 출제 영역(클러스터 아키텍처, 워크로드/스케줄링, 서비스/네트워킹, 스토리지, 트러블슈팅)을 로컬 환경(`Kind` + `Multipass kubeadm`)에서 100% 실습으로 체득합니다.

---

## 1. CKA 출제 비중 및 로컬 학습 매핑

| CKA 도메인 영역 | 시험 비중 | 본 커리큘럼 매핑 모듈 | 실습 환경 |
| :--- | :---: | :--- | :--- |
| **Cluster Architecture, Installation & Configuration** | **25%** | Module 1, Module 6, Module 7 | `Kind` + `Multipass (kubeadm)` |
| **Workloads & Scheduling** | **15%** | Module 2, Module 3 | `Kind` (Multi-node) |
| **Services & Networking** | **20%** | Module 4 | `Kind` (Calico/Cilium CNI) |
| **Storage** | **10%** | Module 5 | `Kind` |
| **Troubleshooting** | **30%** | Module 8 (전 과정 상시 적용) | `Kind` + `Multipass (kubeadm)` |

---

## 2. 상세 학습 모듈 (Step-by-Step Modules)

### Module 1: 클러스터 아키텍처 이해 및 로컬 멀티 노드 구축
- **이론(Why & How)**
  - Control Plane 컴포넌트(`kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager`)와 Worker Node 컴포넌트(`kubelet`, `kube-proxy`, Container Runtime)의 통신 흐름 이해
  - Pod가 생성될 때 각 컴포넌트가 주고받는 이벤트 순서 파악
- **실습(What)**
  - `k8s/00-cluster/kind-config.yaml`: Control Plane 1대 + Worker Node 2대로 구성된 멀티 노드 클러스터 정의 및 포트 매핑(Ingress 연동용 80/443)
  - `kubectl config`를 활용한 Context, Cluster, User 전환 및 관리
- **CKA 핵심 포인트**
  - Static Pod의 개념과 `/etc/kubernetes/manifests` 경로 이해
  - `kubectl api-resources`, `kubectl explain <resource>.<field>`를 활용한 공식 문서 없이 스펙 찾는 법

### Module 2: 핵심 워크로드와 샘플 앱 배포 (Workloads)
- **이론(Why & How)**
  - 왜 Pod를 직접 만들지 않고 `ReplicaSet`과 `Deployment`를 사용하는가?
  - 선언적(Declarative) 상태 유지 원리와 RollingUpdate / Rollback 메커니즘
- **실습(What)**
  - `app/`: 실습용 경량 웹 애플리케이션(환경변수, 헬스체크 `/healthz`, `/readyz`, 파일 읽기/쓰기 엔드포인트 포함) 및 멀티 스테이지 `Dockerfile` 작성
  - `k8s/01-workloads/`:
    - `namespace.yaml`: 논리적 격리 공간 생성
    - `deployment.yaml`: 샘플 앱 배포, 리소스 요청/제한(`resources.requests/limits`), Liveness/Readiness/Startup Probe 구성
    - `daemonset.yaml`, `job.yaml`, `cronjob.yaml`: 특수 목적 워크로드 실습
- **CKA 핵심 포인트**
  - `kubectl rollout status/history/undo`를 통한 무중단 배포 및 롤백
  - Sidecar 컨테이너 및 InitContainer 구성 패턴 (로그 수집기/초기화 작업)

### Module 3: 고급 스케줄링 및 설정 관리 (Scheduling & Configuration)
- **이론(Why & How)**
  - 애플리케이션 이미지와 환경 설정(Config/Secret)을 분리해야 하는 이유 (12-Factor App 원칙)
  - 특정 노드에 Pod를 배치하거나 배제하는 스케줄러 알고리즘 이해
- **실습(What)**
  - `k8s/02-config/`: `ConfigMap`과 `Secret`을 생성하고 샘플 앱에 환경변수(`env`, `envFrom`) 및 볼륨 마운트(`volumeMounts`)로 주입
  - `k8s/03-scheduling/`:
    - `nodeSelector`, `nodeAffinity`, `podAntiAffinity`(고가용성 배치) 실습
    - `Taints`와 `Tolerations`를 활용해 특정 노드에 일반 Pod 스케줄링 차단 실습
- **CKA 핵심 포인트**
  - Control Plane 노드의 기본 Taint(`node-role.kubernetes.io/control-plane:NoSchedule`) 해제 및 적용

### Module 4: 서비스와 클러스터 네트워킹 (Services & Networking)
- **이론(Why & How)**
  - Pod IP는 왜 휘발성인가? `Service`(`ClusterIP`, `NodePort`, `LoadBalancer`)와 `kube-proxy`(iptables/IPVS)의 동작 원리
  - 클러스터 내부 DNS(`CoreDNS`) 레코드 규칙 (`<svc>.<ns>.svc.cluster.local`)
  - L7 트래픽 라우팅을 위한 `Ingress`와 차세대 표준인 **Gateway API** 비교
  - Zero-Trust 보안을 위한 `NetworkPolicy` (CNI 플러그인 역할)
- **실습(What)**
  - `k8s/04-networking/`:
    - 샘플 앱 노출을 위한 `service.yaml` 및 NGINX Ingress Controller 연동 `ingress.yaml` 작성
    - 프론트엔드/백엔드/DB 간 트래픽을 통제하는 `network-policy.yaml` 작성 (Kind에 Calico 또는 Cilium CNI 적용 실습 포함)
- **CKA 핵심 포인트**
  - `NetworkPolicy`의 `ingress`(들어오는 트래픽) / `egress`(나가는 트래픽) 규칙 및 `namespaceSelector` + `podSelector` 조합 문법 완벽 숙지 (시험 단골 문제)
  - `nslookup` / `dig` 임시 파드를 띄워 CoreDNS 및 Service 연결성 디버깅하기

### Module 5: 영구 스토리지 관리 (Storage)
- **이론(Why & How)**
  - 컨테이너 파일시스템의 휘발성과 `Volume`, `PersistentVolume(PV)`, `PersistentVolumeClaim(PVC)`의 생명주기 분리
  - 정적 프로비저닝(Static) vs `StorageClass`를 통한 동적 프로비저닝(Dynamic Provisioning)
- **실습(What)**
  - `k8s/05-storage/`: `pv.yaml`, `pvc.yaml`, `storageclass.yaml` 작성 후 샘플 앱에 연결하여 파드가 재시작되어도 데이터가 유지되는지 검증
- **CKA 핵심 포인트**
  - `accessModes`(`ReadWriteOnce`, `ReadWriteMany`) 매칭 조건, `persistentVolumeReclaimPolicy`(`Retain`, `Delete`), PVC 용량 확장 실습

### Module 6: 클러스터 보안 및 접근 제어 (RBAC & Security)
- **이론(Why & How)**
  - Kubernetes API 요청의 3단계 관문: **Authentication(인증) → Authorization(인가/RBAC) → Admission Control**
  - `ServiceAccount`와 `Role`/`ClusterRole`, `RoleBinding`/`ClusterRoleBinding`의 관계
- **실습(What)**
  - `k8s/06-security/`:
    - 특정 네임스페이스의 Pod만 조회할 수 있는 최소 권한 `ServiceAccount`와 `Role`, `RoleBinding` 작성
    - 컨테이너가 Root 권한으로 실행되지 않도록 강제하는 `SecurityContext` 적용
- **CKA 핵심 포인트**
  - `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>` 명령어를 통한 권한 검증

### Module 7: CKA 전용 클러스터 운영 (kubeadm, Upgrade, etcd, Maintenance)
- **이론 & 실습 환경**: 이 모듈은 `Multipass`를 통해 로컬에 띄운 가벼운 Ubuntu VM 2대(Control Plane 1, Worker 1)에서 진행합니다.
- **실습 내용**:
  1. **`kubeadm` 클러스터 구축**: containerd 설치, 커널 파라미터 설정, `kubeadm init`, CNI 설치, `kubeadm join`
  2. **클러스터 무중단 버전 업그레이드**:
     - `kubectl drain <node> --ignore-daemonsets` (노드 비우기 및 스케줄링 중단)
     - `kubeadm upgrade plan` & `kubeadm upgrade apply`
     - `kubelet` 및 `kubectl` 패키지 업그레이드 후 `kubectl uncordon <node>`
  3. **`etcd` 백업 및 복구**:
     - `ETCDCTL_API=3 etcdctl snapshot save` (CA 인증서, 서버 인증서, 키 경로 지정)
     - 장애 상황을 가정한 `etcdctl snapshot restore` 및 Static Pod 경로 수정

### Module 8: 실전 트러블슈팅 시나리오 (Troubleshooting - 시험 30% 비중)
- **실습 방식**: 에이전트가 의도적으로 고장 난(Broken) 클러스터나 매니페스트를 제시하면, 학습자가 원인을 찾아 복구하는 모의고사 형태로 진행합니다.
  - 시나리오 1: `ImagePullBackOff`, `CrashLoopBackOff`, `Pending` 상태의 파드 원인 분석 및 복구
  - 시나리오 2: Service로 트래픽이 전달되지 않는 현상 (Label Selector 불일치, `targetPort` 오류, NetworkPolicy 차단) 해결
  - 시나리오 3: Worker Node가 `NotReady` 상태일 때 SSH 접속 후 `systemctl status kubelet`, `journalctl -u kubelet` 로그를 분석하여 설정 파일(`/var/lib/kubelet/config.yaml`) 오류 수정
  - 시나리오 4: Control Plane Static Pod(`kube-apiserver`, `kube-scheduler`) 매니페스트 오타로 인한 API 서버 다운 복구

