# k8s-practice

FastAPI 앱을 minikube 위에서 Docker → K8s 매니페스트 → Helm → Ingress → ArgoCD(GitOps) 순으로 배포해 본 실습 레포.

## 구조

```
app/                  FastAPI 앱 + Dockerfile
k8s/                  초기 원본 매니페스트 (Helm 전환 이후 미사용)
helm/my-app/          Helm 차트 (Deployment, Service, Ingress, PVC)
argocd/               ArgoCD Application 정의
.github/workflows/    이미지 빌드/푸시 + Helm 이미지 태그 갱신
```

## 배포 흐름 (GitOps)

1. `app/` 변경을 `main`에 push
2. GitHub Actions가 이미지를 빌드해 `ghcr.io/lee-dongwook/k8s-practice:<short-sha>` (+ `latest`)로 push
3. 같은 워크플로가 `helm/my-app/values.yaml`의 `image.tag`를 해당 sha로 커밋
4. ArgoCD가 변경을 감지해 자동 sync (prune + selfHeal)

워크플로는 `app/**`, `.github/workflows/**` 변경에만 실행되므로 태그 갱신 커밋이 다시 빌드를 트리거하지 않는다.

## 진행 과정

1. **Docker 이미지 + K8s 매니페스트** — `k8s-app:v2` 로컬 이미지를 `imagePullPolicy: Never`로 Deployment(replicas 2 → 4) + NodePort Service로 배포
2. **GitHub Actions** — main push 시 GHCR로 이미지 빌드/푸시, `docker/metadata-action`으로 `latest` + sha 태그 생성
3. **Helm 차트화** — `helm/my-app`으로 전환, `helm install my-release`로 배포
4. **Ingress** — minikube `ingress` 애드온 + `my-app.local` 호스트 규칙
5. **PVC** — 1Gi RWO PVC를 `/app/data`에 마운트
6. **ArgoCD 도입**
   - 설치 후 접속 불가 → `argocd-server`가 ClusterIP라 외부 노출 안 됨 + 서버 Pod 재시작으로 기존 port-forward가 끊김
   - 점검 결과: ArgoCD Application 미등록, PVC 커밋이 클러스터에 미반영(Helm revision 6에 PVC 없음), `helm test` 대상 서비스명 불일치(`my-release-my-app` vs `my-release-service`), `latest` 태그라 변경 감지 불가
   - `argocd/application.yaml` 등록 (`releaseName: my-release`로 기존 리소스 인수) → sync 시 PVC 생성/Bound 확인
   - test-connection 대상 서비스명 수정
   - ArgoCD는 `helm template`으로 렌더링하므로 Helm CLI release 기록(`sh.helm.release.v1.my-release.*` 시크릿)이 낡은 상태로 남음 → 삭제. 이후 `helm upgrade/uninstall`은 사용하지 않는다
   - CI가 `values.yaml` 태그를 커밋 sha로 갱신하도록 변경, `pullPolicy: IfNotPresent`

## 로컬 접속 (macOS, docker 드라이버)

docker 드라이버에선 노드 IP(192.168.49.2)에 호스트에서 직접 접근할 수 없다.

```bash
# 앱 (Ingress)
echo "127.0.0.1 my-app.local" | sudo tee -a /etc/hosts   # 최초 1회
minikube tunnel                                           # 별도 터미널에서 유지
open http://my-app.local

# ArgoCD UI
kubectl -n argocd port-forward svc/argocd-server 8080:443   # https://localhost:8080
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

## 시작 / 종료

```bash
minikube start   # 재시작 시 ArgoCD가 Git 상태로 자동 복구
minikube stop
```
