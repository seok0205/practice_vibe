# Module 1: Kubernetes 클러스터 아키텍처 및 로컬 멀티 노드 구축

> **학습 목표**: Kubernetes 클러스터를 구성하는 Control Plane과 Worker Node의 내부 컴포넌트 역할 및 통신 원리를 완벽히 이해하고, `Kind`를 사용해 **Control Plane 1대 + Worker Node 2대**로 구성된 멀티 노드 클러스터를 직접 구축하고 탐색합니다.

---

## 1. 개념과 원리 (Why & How): Kubernetes는 어떻게 동작하는가?

Docker만 사용할 때는 단일 서버에서 `docker run` 명령어로 컨테이너를 직접 띄웠습니다. 하지만 서버가 수십 대로 늘어나면 **"어느 서버에 여유 메모리가 있는지?", "서버가 죽으면 그 위의 컨테이너를 누가 다른 서버로 옮겨줄 것인지?", "컨테이너 간 네트워크 통신은 어떻게 연결할 것인지?"**를 사람이 일일이 관리할 수 없습니다.

이를 해결하기 위해 Kubernetes는 클러스터를 **두뇌 역할을 하는 Control Plane(마스터 노드)**과 **실제 일꾼 역할을 하는 Worker Node(워커 노드)**로 분리하여 운영합니다.

### 1.1 클러스터 아키텍처 및 컴포넌트 통신 흐름

> **핵심 원칙 (Hub-and-Spoke 패턴)**: Kubernetes의 모든 컴포넌트는 오직 **`kube-apiserver`**와만 통신합니다. 심지어 클러스터의 모든 데이터를 저장하는 데이터베이스인 **`etcd`조차도 오직 `kube-apiserver`만 직접 읽고 쓸 수 있습니다.**

```mermaid
flowchart TB
    User["사용자 / 관리자 (kubectl)"] -->|1. YAML 제출 (HTTPS/REST)| API

    subgraph ControlPlane["Control Plane (마스터 노드)"]
        API["kube-apiserver\n(유일한 통신 창구 / 인증·인가·검증)"]
        ETCD[("etcd\n(클러스터 상태 Key-Value 저장소)")]
        SCHED["kube-scheduler\n(최적의 Worker Node 배정)"]
        CM["kube-controller-manager\n(Desired State == Current State 유지)"]

        API <-->|2. 상태 저장 및 조회| ETCD
        SCHED <-->|3. 미배정 Pod 감시 및 노드 지정| API
        CM <-->|4. 레플리카 수/노드 상태 감시 및 조정| API
    end

    subgraph WorkerNodes["Worker Nodes (워커 노드 1, 2)"]
        KUBELET["kubelet\n(노드 에이전트: CRI를 통해 컨테이너 생성/감시)"]
        PROXY["kube-proxy\n(네트워크 규칙: Service IP -> Pod IP 라우팅)"]
        CRI["Container Runtime (containerd)\n(실제 컨테이너 실행)"]
        POD["App Pods"]

        API <-->|5. 내 노드에 배정된 Pod 생성 지시 및 상태 보고| KUBELET
        API -->|Service/Endpoint 변경 감시| PROXY
        KUBELET -->|컨테이너 생성 명령| CRI
        CRI --> POD
    end
```

### 1.2 사용자가 `kubectl apply -f pod.yaml`을 입력했을 때 일어나는 일 (6단계)

1. **`kubectl` → `kube-apiserver`**: 사용자가 요청을 보내면 `kube-apiserver`가 인증(Authentication) → 인가(Authorization/RBAC) → Admission Control을 거쳐 요청이 유효한지 검사합니다.
2. **`kube-apiserver` → `etcd`**: 검증이 통과되면, "이러한 Pod를 만들어야 한다(Desired State)"는 정보를 `etcd`에 기록합니다. (아직 컨테이너가 실행된 것도, 어느 노드로 갈지 정해진 것도 아닙니다. `nodeName` 필드가 비어 있는 `Pending` 상태입니다.)
3. **`kube-scheduler`의 개입**: `kube-apiserver`를 감시(Watch)하던 `kube-scheduler`가 `nodeName`이 비어 있는 새 Pod를 발견합니다. 각 워커 노드의 남은 CPU/메모리, Taint, Affinity 조건을 계산(Filtering & Scoring)하여 가장 적합한 노드(예: `worker-1`)를 선택한 뒤 `kube-apiserver`에 알려줍니다.
4. **`etcd` 업데이트**: `kube-apiserver`는 `etcd`에 있는 해당 Pod 정보에 `nodeName: worker-1`을 기록합니다.
5. **`kubelet`의 실행**: `worker-1` 노드에서 실행 중이던 에이전트인 **`kubelet`**이 자신의 노드에 새로운 Pod가 배정된 것을 감지합니다. `kubelet`은 컨테이너 런타임(**`containerd`**)에 이미지를 받아와 컨테이너를 띄우라고 명령합니다.
6. **상태 보고**: 컨테이너가 정상 실행되면 `kubelet`이 현재 상태(`Running`)를 다시 `kube-apiserver`에 보고하고, `etcd`에 최종 반영됩니다.

---

## 2. CKA 시험 필수 핵심 포인트 (Static Pod vs DaemonSet vs Systemd)

CKA 트러블슈팅 문제(30% 비중)를 풀기 위해서는 **"Control Plane 컴포넌트들은 도대체 누가 띄워주는가?"**를 반드시 알아야 합니다.

| 구분 | 구동 방식 | 관리 주체 및 설정 파일 경로 (CKA 암기 필수!) |
| :--- | :--- | :--- |
| **`kubelet`** | Linux **Systemd 데몬**으로 직접 실행 | 왜냐하면 Pod를 띄우는 주체가 `kubelet`이므로 자기 자신은 컨테이너가 아닌 OS 프로세스로 떠야 합니다.<br>- 상태 확인: `systemctl status kubelet`<br>- 로그 확인: `journalctl -u kubelet`<br>- 설정 경로: `/var/lib/kubelet/config.yaml` |
| **`kube-apiserver`<br>`etcd`<br>`kube-scheduler`<br>`kube-controller-manager`** | **Static Pod (스태틱 파드)** | API 서버가 아직 없는데 कैसे Pod를 띄울까요? 마스터 노드의 `kubelet`이 특정 디렉토리(**`/etc/kubernetes/manifests/`**)에 있는 YAML 파일을 직접 읽어서 API 서버 없이 스스로 띄우는 특수한 Pod를 **Static Pod**라고 합니다.<br>- 특징: 파드 이름 끝에 항상 `-<노드이름>`이 자동으로 붙습니다.<br>- 수정 방법: `/etc/kubernetes/manifests/*.yaml` 파일을 수정하고 저장하면 `kubelet`이 감지하여 즉시 파드를 재시작합니다. |
| **`kube-proxy`<br>CNI (`calico`, `kindnet`)** | **DaemonSet (데몬셋)** | API 서버가 정상 기동된 후, 클러스터의 모든 노드에 정확히 1개씩 배포되는 일반 Kubernetes 워크로드입니다. |

---

## 3. 실습 (What & Verify): 멀티 노드 클러스터 구축 및 내부 해부

현재 레포지토리의 [`k8s/00-cluster/kind-config.yaml`](../k8s/00-cluster/kind-config.yaml) 파일에 Control Plane 1대 + Worker Node 2대 설정이 작성되어 있습니다. 아래 순서대로 직접 터미널에서 실행하며 결과를 확인해 보세요.

### Step 1: 사전 도구 확인 및 `kind` 설치
현재 Mac에 `docker`와 `kubectl`은 설치되어 있으나 `kind`가 설치되어 있지 않다면 Homebrew로 설치합니다. Also, Docker Desktop(또는 OrbStack)이 실행 중인지 확인하세요.

```bash
# 1. kind 설치 (이미 설치되어 있다면 생략)
brew install kind

# 2. Docker 데몬이 정상 실행 중인지 확인
docker ps
```

### Step 2: 멀티 노드 클러스터 생성
작성된 [`k8s/00-cluster/kind-config.yaml`](../k8s/00-cluster/kind-config.yaml) 파일을 사용해 `vibe-cluster`라는 이름의 3노드 클러스터를 생성합니다.

```bash
# 클러스터 생성 (약 1~2분 소요)
kind create cluster --config k8s/00-cluster/kind-config.yaml
```

### Step 3: 클러스터 노드 및 Context 검증
클러스터가 생성되면 `kubectl`의 바라보는 대상(Context)이 자동으로 `kind-vibe-cluster`로 설정됩니다.

```bash
# 1. 현재 등록된 Context 목록 확인 ('*' 표시가 현재 활성화된 클러스터)
kubectl config get-contexts

# 2. 3개의 노드(control-plane 1, worker 2)가 모두 Ready 상태인지, 부여한 라벨이 잘 들어갔는지 확인
kubectl get nodes -o wide --show-labels
```
> **확인 포인트**: `vibe-cluster-worker`에는 `tier=frontend,zone=ap-northeast-2a`, `vibe-cluster-worker2`에는 `tier=backend,zone=ap-northeast-2c` 라벨이 붙어 있는 것을 확인하세요!

### Step 4: Control Plane 컴포넌트 및 Static Pod 직접 눈으로 확인하기 (CKA 실습)
우리가 배운 컴포넌트들이 실제로 어디서 어떻게 돌고 있는지 확인해 봅시다.

```bash
# 1. 시스템 네임스페이스(kube-system)에 떠 있는 모든 파드 확인
kubectl get pods -n kube-system -o wide
```
출력 결과를 자세히 살펴보세요:
- `etcd-vibe-cluster-control-plane`, `kube-apiserver-vibe-cluster-control-plane`, `kube-controller-manager-...`, `kube-scheduler-...`: 이름 뒤에 노드 이름이 붙어 있는 **Static Pod**들입니다.
- `kindnet-...`, `kube-proxy-...`: 3개의 노드에 각각 1개씩 총 3개가 떠 있는 **DaemonSet** 파드들입니다.
- `coredns-...`: 클러스터 내부 DNS 서버 역할을 하는 **Deployment** 파드입니다.

이제 Control Plane 노드 내부로 직접 들어가서 진짜로 `/etc/kubernetes/manifests` 폴더에 Static Pod YAML 파일들이 있는지 확인해 봅시다! (`Kind`에서는 각 노드가 Docker 컨테이너로 돌아가므로 `docker exec`로 노드에 접속할 수 있습니다.)

```bash
# 2. Control Plane 노드의 /etc/kubernetes/manifests 디렉토리 조회
docker exec -it vibe-cluster-control-plane ls -la /etc/kubernetes/manifests
```
> `etcd.yaml`, `kube-apiserver.yaml`, `kube-controller-manager.yaml`, `kube-scheduler.yaml` 4개의 파일이 보일 것입니다! CKA 시험에서는 이 파일들에 오타가 나서 클러스터가 먹통이 된 상황을 주고 고치라는 문제가 자주 출제됩니다.

### Step 5: CKA 필수 스킬 - 공식 문서 없이 스펙 검색하기 (`kubectl explain`)
CKA 시험이나 실무에서 YAML의 특정 필드 이름이 기억나지 않을 때 가장 빠른 방법은 `kubectl explain`입니다.

```bash
# 1. 클러스터가 지원하는 모든 리소스와 단축어(SHORTNAMES) 확인
kubectl api-resources

# 2. Node 리소스의 spec 하위 필드 설명 확인
kubectl explain node.spec

# 3. Control Plane 노드에 어떤 Taint가 걸려 있는지 확인 (일반 파드가 마스터 노드에 안 뜨는 이유)
kubectl describe node vibe-cluster-control-plane | grep -A 5 -i taint
```
> `Taints: node-role.kubernetes.io/control-plane:NoSchedule`을 확인하셨다면 Module 1의 핵심 개념을 완벽히 검증하신 것입니다!

