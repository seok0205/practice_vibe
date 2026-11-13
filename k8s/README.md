# k8s/ - 순수 Kubernetes 매니페스트 및 CKA 실습 디렉토리

이 디렉토리는 **Phase 1 (Kubernetes & CKA)** 과정에서 작성하는 모든 순수 Kubernetes YAML 파일과 로컬 클러스터(`Kind`) 설정 파일이 위치하는 공간입니다.

## 하위 폴더 구성 (예정)
- `00-cluster/`: `Kind` 멀티 노드 클러스터 설정(`kind-config.yaml`) 및 CNI 설정
- `01-workloads/`: `Namespace`, `Deployment`, `DaemonSet`, `Job`, `CronJob` 실습 매니페스트
- `02-config/`: `ConfigMap`, `Secret` 주입 실습 매니페스트
- `03-scheduling/`: `nodeAffinity`, `podAntiAffinity`, `Taints & Tolerations` 실습 매니페스트
- `04-networking/`: `Service`, `Ingress`, `NetworkPolicy` 실습 매니페스트
- `05-storage/`: `PV`, `PVC`, `StorageClass` 실습 매니페스트
- `06-security/`: `ServiceAccount`, `Role`, `RoleBinding`, `SecurityContext` 실습 매니페스트

> **작성 규칙 (`AGENTS.md` 준수)**: 이 폴더에 작성되는 모든 `.yaml` 파일은 상단 아키텍처 설명과 주요 필드별 한국어 주석(원리, 기본값, CKA 시험 팁)을 반드시 포함해야 합니다.
>
> 관련 커리큘럼: [`../curriculum/01-kubernetes-and-cka.md`](../curriculum/01-kubernetes-and-cka.md)

