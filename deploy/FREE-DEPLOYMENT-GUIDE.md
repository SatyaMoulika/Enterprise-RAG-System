# Deploying Atlas with free resources

This guide is for the current RAG application when you have no purchased server or domain. It explains how to share the application from your existing Ubuntu computer, how to give a small group private access, and how to move it to a free cloud VM if you can obtain one. Commands assume Bash and run from the project directory unless another location is stated.

**Start with your existing computer and a temporary HTTPS tunnel.** This keeps PostgreSQL, uploaded files and the Ollama models on hardware you already have. You do not need a paid AI API, a purchased domain or a rented server for that route. Your computer must remain on and connected while others use it. Electricity and internet usage still apply.

Provider information was checked on **24 November 2026**. Free plans can change; verify the linked official pages before creating resources. A free demo is achievable. Guaranteed uptime, cloud capacity and dependable employee production hosting are not guaranteed by these options.

## Contents

1. [Choose a route](#1-choose-a-route)
2. [Understand what must run](#2-understand-what-must-run)
3. [Prepare the local application for sharing](#3-prepare-the-local-application-for-sharing)
4. [Route A: temporary public HTTPS demo](#4-route-a-temporary-public-https-demo)
5. [Route B: private access with Tailscale](#5-route-b-private-access-with-tailscale)
6. [Route C: free cloud VM and free DNS name](#6-route-c-free-cloud-vm-and-free-dns-name)
7. [Create accounts and verify document access](#7-create-accounts-and-verify-document-access)
8. [Password recovery without SMTP](#8-password-recovery-without-smtp)
9. [Back up the demo](#9-back-up-the-demo)
10. [Back up and restore cloud hosting](#10-back-up-and-restore-cloud-hosting)
11. [Update and restart](#11-update-and-restart)
12. [Monitor resources and answer quality](#12-monitor-resources-and-answer-quality)
13. [Troubleshoot](#13-troubleshoot)
14. [Cost controls and completion checklist](#14-cost-controls-and-completion-checklist)

## 1. Choose a route

| Route | Where the application runs | Address | Suitable use | Main dependency |
| --- | --- | --- | --- | --- |
| A: Cloudflare Quick Tunnel | Your existing computer | Temporary HTTPS `trycloudflare.com` address | Short demo, interview, project review | Computer and tunnel stay running |
| B: Tailscale Serve | Your computer, or a VM | Private HTTPS `ts.net` address | Personal project with a few trusted testers | Each tester needs authorized Tailscale access |
| C: Oracle Always Free VM plus Duck DNS | A provisioned cloud VM | HTTPS `your-name.duckdns.org` | Longer-running prototype independent of your computer | Account verification, available free VM capacity, ongoing maintenance |

Route A requires neither a Cloudflare account nor a domain. Its hostname changes when the tunnel is recreated. Quick Tunnels are intended for development/testing and have no uptime guarantee. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

Route B uses a Tailscale account. Its current Personal plan lists six users at no subscription charge; check eligibility for your intended use. Treat this as a personal project route, not a promise of a free company deployment. [Tailscale pricing](https://tailscale.com/pricing)

Route C requires a cloud account. Oracle requires supported card details for identity verification and can place a temporary authorization hold. If you cannot provide a card or accept a hold, use Route A or B. Always Free resources and time-limited trial credits are different offers. [Oracle Free Tier FAQ](https://www.oracle.com/cloud/free/faq/)

### Why a free frontend host alone is insufficient

This application has persistent uploads, a database, an ingestion worker and local AI inference. Uploading only `web/dist` to a static host gives you the interface without the services it needs. The browser calls `/api` on the same origin, so a split frontend/backend deployment also requires routing changes.

Render's free web services lose local files on restart/redeploy, cannot attach persistent disks, and spin down when idle. Its free PostgreSQL expires after 30 days. That combination does not preserve this application's uploaded files and database as currently designed. This is an architectural fit assessment, not a claim that Render cannot host a redesigned application. [Render free service limitations](https://render.com/docs/free)

Do not plan to run Ollama and its model weights inside a static-site host or a short-lived frontend function. Using hosted AI instead would require a different provider integration and its own quota/privacy review; that is outside this guide.

## 2. Understand what must run

| Component | Purpose | Persistent data |
| --- | --- | --- |
| `web` | React interface and Nginx `/api` proxy | Built application assets |
| `api` | Authentication, document access and question answering | Uses database and upload volume |
| `ingestion_worker` | Extracts, chunks and indexes uploaded documents | Uses the same database/uploads |
| `postgres` | Users, workspaces, document records, chunks and embeddings | `rag_postgres` volume |
| `ollama` | Runs `all-minilm` embeddings and `qwen2.5:3b` generation | `rag_models` volume |
| Caddy, Route C only | Public HTTPS reverse proxy | Certificate state volumes |

For Routes A/B, the request path is: visitor → HTTPS tunnel/private proxy → local port 8080 → Nginx → API → PostgreSQL/Ollama. The worker indexes in the background. Expose the web application, not PostgreSQL, Ollama or the raw API.

### Practical resource planning

For this exact small-model configuration, use **12 GB RAM or more if available**, a modern multi-core CPU and roughly **20–30 GB of free disk as an initial planning allowance**. These are engineering estimates, not measured minimums or an SLA. Documents, backups, Docker builds and logs increase disk use. Larger contexts and simultaneous inference increase memory use.

Start with one question at a time and a few small text-based PDFs. CPU-only inference can be slow. Check actual performance on the chosen machine before inviting more users. Keep the optional cross-encoder reranker disabled initially.

```bash
free -h
df -h /
docker compose version
docker info
```

The demo and production overlays require Docker Compose **2.24.4 or newer**, or a newer compatible release, because they use `!reset`. Existing Docker installations need not be reinstalled if they work and meet this requirement.

## 3. Prepare the local application for sharing

### 3.1 Use the existing checkout and project name

On your current computer:

```bash
cd /home/moulika/Desktop/Personal/RAG-App-Updated
docker compose -p rag-updated ps
```

Use **`rag-updated` consistently**. Omitting `-p rag-updated` previously created a second stack and caused a port conflict. A different project name also selects different named volumes, which can make your documents appear missing.

Do not overwrite an existing `.env`, replace an existing database password, or remove volumes. Environment files contain secrets; do not paste their contents into screenshots or chat.

### 3.2 Sign in before disabling signup

Confirm you can sign in as an administrator at `http://localhost:8080`. If this is a fresh installation with no account, use the operator command after starting the API:

```bash
docker compose -p rag-updated exec api \
  .venv/bin/python scripts/create_workspace.py \
  --name 'Atlas Demo' --email your-real-email@example.com
```

Replace the example email. The command prompts for a password of at least 12 characters and its confirmation. Do not create another administrator if your existing account already works. Creating a fresh workspace does not automatically isolate an administrator's old workspace data from that old account.

Use synthetic documents for internet demos. The existing local stack contains your existing accounts/documents; applying an overlay does not sanitize them or copy them into a separate environment.

### 3.3 Apply the sharing overlay before starting any tunnel

`compose.demo.yaml` is included with this guide. It:

- Disables direct email-only password reset, including its backend endpoint.
- Disables public workspace registration; administrators can still create members.
- Removes the API's host port mapping. Nginx continues to reach the API internally.
- Leaves the frontend bound to `127.0.0.1:8080` for a host-based tunnel.
- Sets restart policies and limits each service's Docker logs to three 10 MB files.

**The local email-only reset feature must not be exposed to visitors.** It deliberately provides no proof of mailbox ownership. Merely hiding its link would leave the backend vulnerable, so this overlay disables it server-side.

Define this convenience function in your terminal. Re-run the definition in each new terminal; it is not automatically permanent:

```bash
demo() {
  docker compose -p rag-updated \
    -f compose.yaml -f compose.demo.yaml "$@"
}
```

Then validate and start:

```bash
demo config --quiet
demo up -d --build
demo ps
demo exec ollama ollama pull all-minilm
demo exec ollama ollama pull qwen2.5:3b
```

Existing model downloads are reused. If the API fails, inspect `demo logs --tail=100 api`; the worker waits for API health. Starting containers successfully does not prove model inference works.

### 3.4 Verify the sharing configuration

```bash
curl --fail http://127.0.0.1:8080/api/ready
curl --fail http://127.0.0.1:8080/api/auth/config
```

Expected responses include:

```json
{"status":"ready","inference":"checked on use"}
```

```json
{"registration_enabled":false,"direct_password_reset_enabled":false}
```

Also verify that direct reset is blocked, using a nonexistent synthetic address:

```bash
curl -i http://127.0.0.1:8080/api/auth/reset-password/direct \
  -H 'Content-Type: application/json' \
  --data '{"email":"nonexistent-demo@example.com","password":"unused-demo-password-123"}'
```

Expect **HTTP 403** and `Direct password reset is disabled.` Do not continue if the configuration says direct reset is enabled. If the proxy returns 429 because of repeated checks, wait before retrying.

### 3.5 Understand the difference from the VPS profile

For a tunnel, use **base + demo**. For a publicly reachable cloud server with DNS, use **base + production**. Do not combine both overlays. The production profile requires a domain setting and starts Caddy; the demo profile relies on the tunnel/private proxy for HTTPS.

Always use the same profile for subsequent `up` commands. Running plain `docker compose -p rag-updated up -d` later can re-enable the default local shortcut. A plain `ps` does not change configuration; `up` can.

## 4. Route A: temporary public HTTPS demo

This route shares the application already running on your computer. There is no cloud VM to rent. Your database and models stay local, but visitors' traffic passes through the tunnel provider; uploaded content and answers are accessible to authorized application users through that path.

### 4.1 Install cloudflared on Ubuntu

Skip installation if a current `cloudflared --version` already works. Otherwise, use Cloudflare's package repository:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install cloudflared
cloudflared --version
```

These install system software and require your Ubuntu administrator password. Use the current official instructions if package/key details change. [Cloudflare package installation](https://pkg.cloudflare.com/index.html)

### 4.2 Start a restricted demo tunnel

After Section 3 passes, open a second terminal and run:

```bash
cloudflared tunnel --url http://localhost:8080 \
  --allowed-mail your-real-email@example.com \
  --allowed-mail tester@example.com
```

Replace both addresses with actual permitted visitors. Current Quick Tunnel documentation supports `--allowed-mail`: visitors authenticate with an emailed one-time PIN before reaching your app. Cloudflare sends that PIN, so your app needs no SMTP configuration for this outer gate. Visitors then sign in separately to Atlas. If an older binary rejects the flag, update it before sharing the link. [Quick Tunnel email restrictions](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

The terminal prints a URL similar to `https://random-words.trycloudflare.com`. Open the actual printed URL, not this example. Leave that terminal running. No inbound router port forwarding or purchased domain is needed.

### 4.3 Set the public application URL

In the terminal where you defined `demo`, set the actual address:

```bash
export DEMO_PUBLIC_APP_URL='https://replace-with-your-actual.trycloudflare.com'
demo up -d api ingestion_worker
```

This updates application configuration without rebuilding code or changing secrets. The origin is mostly relevant to email links; direct reset remains disabled regardless. If the tunnel URL changes, repeat this step. The exported variable lasts only in that terminal; put `DEMO_PUBLIC_APP_URL` in your private root `.env` if you want the same value used by other terminals, and update it after recreating the tunnel.

### 4.4 Test from outside your computer

Use your phone with Wi-Fi disabled, or ask an allowed tester on another network:

1. Open the printed HTTPS URL and complete the outer email PIN check.
2. Sign in with a pre-created Atlas account.
3. Verify Overview, My documents and Ask documents load.
4. Upload a small synthetic text PDF as an administrator; wait for indexing to finish.
5. Ask a question with a known answer and inspect its supporting passage.
6. Select **Ask about this** on one document and confirm the answer/citations stay scoped to it.
7. Verify a member cannot retrieve another member's private letter.

The email gate requires a browser interaction; an unauthenticated command-line request to the public URL can receive the gate page rather than API JSON.

### 4.5 Stop sharing

Press **Ctrl+C** in the cloudflared terminal. That tunnel URL stops working; the local containers remain available to you. You can also stop the app using `demo stop` and resume with `demo up -d`.

Quick Tunnels currently limit simultaneous in-flight requests to 200 and do not support SSE. This app currently uses ordinary JSON chat responses, so it does not rely on SSE. Your machine's inference capacity will usually be the practical limit long before 200 requests. [Quick Tunnel limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

Use this for scheduled demos. A changing URL and a computer that can sleep are poor foundations for unattended employee access.

## 5. Route B: private access with Tailscale

Choose this if the intended audience is a few trusted people who can install Tailscale. **Serve is private to your authorized tailnet; Funnel is public.** Use Serve here. Tailscale supplies an HTTPS address, so a purchased domain is unnecessary. [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)

1. Create an eligible Personal account and install Tailscale on the hosting computer using the [official Linux installation instructions](https://tailscale.com/download/linux).
2. Authenticate the host using `sudo tailscale up` and complete browser login.
3. Apply and verify the demo overlay from Section 3; direct reset must stay disabled even for remote private testers.
4. Invite the intended testers to the tailnet, within your current plan allowance. Each tester installs and signs in to Tailscale. Invitation and access policies determine whether they can reach the host.
5. On the host, run:

```bash
sudo tailscale serve --bg http://127.0.0.1:8080
tailscale serve status
```

Follow any prompts to enable the necessary HTTPS settings. Use the exact HTTPS URL displayed by the command, usually a host under your `ts.net` name. The `--bg` flag runs the proxy in the background; check its status after reboot. [Serve command reference](https://tailscale.com/docs/reference/tailscale-cli/serve)

6. Set the displayed URL as `DEMO_PUBLIC_APP_URL`, then run `demo up -d api ingestion_worker`.
7. Test from another authorized device, including app sign-in and document permissions.

To remove this host's Serve configuration:

```bash
sudo tailscale serve reset
```

That command clears Serve configuration on the device; check for any unrelated existing Serve services before using it. The host computer still needs to stay on, and users still need Atlas accounts. Tailscale access does not create application members.

If you deliberately need a public `ts.net` address, Tailscale also offers Funnel, with separate enablement and bandwidth restrictions. Do not substitute it accidentally for Serve. See [Funnel documentation](https://tailscale.com/docs/features/tailscale-funnel) before choosing it.

## 6. Route C: free cloud VM and free DNS name

Use this only if the app must continue running when your own computer is off. This route deploys a fresh environment; your local accounts/files do not migrate automatically.

### 6.1 Obtain an eligible VM

Oracle's current Always Free documentation lists **2 Ampere A1 OCPUs and 12 GB RAM**, equivalent to 1,500 OCPU-hours and 9,000 GB-hours monthly, and **200 GB combined boot/block storage** in the home region. Older tutorials mentioning 4 OCPUs/24 GB do not match the current published allowance for Always Free tenancies. Free capacity can be unavailable; idle instances can be reclaimed. [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

Recommended initial selection for this prototype:

| Setting | Selection |
| --- | --- |
| Account | Free Tier; do not upgrade merely to obtain capacity |
| Region | Your chosen home region with eligible capacity |
| OS | Official Ubuntu 24.04 LTS image compatible with the selected architecture |
| Shape | `VM.Standard.A1.Flex`, ARM64 |
| Allocation | One VM, 2 OCPUs and 12 GB RAM, within your displayed allowance |
| Boot disk | About 80 GB as a starting choice, within total free storage |
| Network | Public subnet, internet gateway and a public IP if using public DNS |
| SSH | Your public key; keep the private key on your own computer |

The 80 GB choice is a planning recommendation, not a provider minimum. Verify every resource's free eligibility in the console. Do not add paid marketplace images, load balancers, extra disks or higher-performance storage options. If the console's eligibility/cost display is unclear, resolve it before provisioning. Budgets notify; they are not a guaranteed spending cap.

If A1 capacity is unavailable, stop and use your computer. Do not assume a tiny 1 GB micro VM can run this model-based stack. A1 is ARM64: verify the images, locked dependencies and actual inference on that architecture. This guide does not claim an ARM deployment has already passed.

For console steps, follow [Oracle's instance creation guide](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm). Create security rules allowing SSH only from your current administrative IP, and public HTTP/HTTPS on TCP 80/443. UDP 443 is optional. Keep ports 5432, 8000, 8001, 8080 and 11434 closed externally. Host firewall rules and cloud network rules must both permit the intended traffic. Preserve SSH access while changing them; do not flush firewall rules blindly.

### 6.2 Connect and install Docker

On your computer, replace the key path and VM address:

```bash
chmod 600 /path/to/your-private-key
ssh -i /path/to/your-private-key ubuntu@YOUR_VM_PUBLIC_IP
```

On the **fresh Ubuntu VM**, install Docker Engine from its official repository. If Docker/containerd is already installed, resolve package conflicts using the official guide before proceeding; do not uninstall a working runtime that hosts other applications.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
  "$(dpkg --print-architecture)" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

These commands install the daemon and Compose plugin; compare with the maintained [Docker Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/) if your OS release differs. The remaining VM examples use `sudo docker`, avoiding changes to Docker group membership.

### 6.3 Transfer the current application source

The current working tree includes uncommitted files. A remote `git clone` or `git pull` will not contain those changes until you commit and push them. Use a reviewed private Git repository containing all required files, or transfer a source snapshot.

For a snapshot, run on **your existing computer**, not the VM:

```bash
cd /home/moulika/Desktop/Personal/RAG-App-Updated
tar --exclude='.git' --exclude='.env' --exclude='.env.*' \
  --exclude='.aws' --exclude='.ssh' --exclude='.codex' \
  --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' \
  --exclude='.pytest_cache' --exclude='.ruff_cache' \
  --exclude='uploads' --exclude='vectorstore' --exclude='backups' \
  --exclude='dist' -czf /tmp/atlas-source.tar.gz .
tar -tzf /tmp/atlas-source.tar.gz | less
scp -i /path/to/your-private-key /tmp/atlas-source.tar.gz \
  ubuntu@YOUR_VM_PUBLIC_IP:/home/ubuntu/atlas-source.tar.gz
```

Review the archive before transfer for private documents or credentials stored under other names. Excluding common secret names is not a substitute for checking your source tree. The snapshot does not include Docker volumes, existing accounts or indexed documents. It includes the frontend vendor package required by the Docker build if that package exists in the checkout.

On the **VM**:

```bash
mkdir -p /home/ubuntu/atlas
tar -xzf /home/ubuntu/atlas-source.tar.gz -C /home/ubuntu/atlas
cd /home/ubuntu/atlas
```

Alternatively, clone your actual private repository into that directory. Do not paste Git access tokens into shell command lines.

### 6.4 Obtain a free DNS name

Duck DNS offers free dynamic DNS. Sign in to [Duck DNS](https://www.duckdns.org/), choose an available subdomain such as `your-unique-atlas-name`, and set its IPv4 address to the VM's public IP. The result is `your-unique-atlas-name.duckdns.org`; you do not own the parent domain.

Confirm resolution from your computer:

```bash
getent ahostsv4 your-unique-atlas-name.duckdns.org
```

The result must point to your VM. Do not add an AAAA record unless the VM actually accepts IPv6 connections. If the VM's IP changes, update Duck DNS; automation is optional and requires protecting its update token. See the [Duck DNS FAQ](https://www.duckdns.org/faqs.jsp). Manual updates avoid storing another credential for the initial prototype.

### 6.5 Create the VM environment file

On the **VM**, from `/home/ubuntu/atlas`:

```bash
mkdir -p /home/ubuntu/.config/atlas
chmod 700 /home/ubuntu/.config/atlas
cp -n deploy/production.env.example /home/ubuntu/.config/atlas/production.env
chmod 600 /home/ubuntu/.config/atlas/production.env
openssl rand -hex 32
openssl rand -hex 32
nano /home/ubuntu/.config/atlas/production.env
```

Use two different generated values for `RAG_DB_PASSWORD` and `JWT_SECRET_KEY`. Keep them private. Set:

```dotenv
PUBLIC_DOMAIN=your-unique-atlas-name.duckdns.org
ACME_EMAIL=your-real-email@example.com
LOCAL_DIRECT_PASSWORD_RESET=false
RERANKER_MODE=none
RAG_INSTALL_RERANKING=false
```

Leave SMTP settings empty if you are not using email recovery. The production override disables direct reset and public signup regardless of local defaults. Do not enter `https://` in `PUBLIC_DOMAIN`; use only the hostname. Keep a secure copy of the environment file separately from database backups.

### 6.6 Launch the cloud stack

Define this function in the VM terminal:

```bash
prod() {
  sudo docker compose \
    --env-file /home/ubuntu/.config/atlas/production.env \
    -p rag-production \
    -f compose.yaml -f compose.production.yaml "$@"
}
```

Use this function for every cloud operation, from `/home/ubuntu/atlas`:

```bash
prod config --quiet
prod up -d --build
prod ps
prod exec ollama ollama pull all-minilm
prod exec ollama ollama pull qwen2.5:3b
prod exec ollama ollama list
```

Caddy is configured to obtain and renew HTTPS certificates for `PUBLIC_DOMAIN`. DNS must already point to the VM and public ports must be reachable. Check `prod logs --tail=100 caddy` if HTTPS does not become available. A Caddy container that is running may still be waiting for certificate issuance.

Create the first administrator:

```bash
prod exec api .venv/bin/python scripts/create_workspace.py \
  --name 'Atlas Demo' --email your-real-email@example.com
```

Open the actual `https://your-unique-atlas-name.duckdns.org` address. Verify:

```bash
curl --fail https://your-unique-atlas-name.duckdns.org/api/ready
curl --fail https://your-unique-atlas-name.duckdns.org/api/auth/config
```

Expected authentication flags are both `false`, as in Section 3.4. Verify certificate validity in the browser, then perform a real upload/question test. On the VM, `prod ps` should show only Caddy publishing public ports, with no public database/model/API ports.

You can now close the SSH session; detached containers continue running while the VM remains available. Restart policies are configured, but provider reclamation, outages and failed services still require monitoring.

### 6.7 Keep the cloud environment separate

`rag-production` creates its own volume namespace. It starts with a fresh database. Re-upload only the documents intended for that environment, or use a controlled database-and-upload restore. Do not copy a running PostgreSQL data directory between machines. Do not change the project name to try to locate local documents.

Before trusting real employee documents to this setup, complete the access and backup checks below. A free VM and HTTPS do not establish document confidentiality or answer correctness by themselves.

## 7. Create accounts and verify document access

The administrator creates employee accounts under **Members**, using an initial password. This currently creates an account immediately; it does not send an invitation. Share credentials separately and privately. Create only a few test accounts initially.

Use at least two distinct member accounts to test separation:

| Test | Expected behavior |
| --- | --- |
| Member A opens their permitted offer letter | File can be opened and used as a source |
| Member B requests Member A's private letter | No unauthorized content is returned |
| A signed-in member asks about “my offer letter” | Available account identity and permitted personal documents determine the context |
| “Ask about this” on a specific PDF | Retrieval and citations stay within that document |
| A question names a person different from the selected document | No invented answer or cross-document leakage |
| A document is deleted | It is no longer retrievable; stale selections are handled |
| A user is removed | Their existing token fails subsequent authenticated requests |
| A scanned image-only PDF is uploaded | An extraction problem is reported rather than assuming OCR exists |

Use separate browser profiles or private windows. Simply switching tabs in one browser can accidentally test the same session. Check both the answer text and the source passages; a plausible answer alone is insufficient.

## 8. Password recovery without SMTP

For **your local, unshared setup**, direct reset is available because you requested it. For **any externally accessible setup**, the guide's profiles disable it. Email plus a new password alone does not identify the owner of an account.

With no SMTP, externally hosted self-service password recovery is unavailable. Cloudflare's optional email PIN gate does not reset Atlas passwords. For the current computer, an operator can recover an account during a maintenance window:

1. Stop the public tunnel and any remote Serve/Funnel access first.
2. Verify no other route exposes the app.
3. Use the original local profile to enable the existing local reset behavior, if its environment settings allow it:

```bash
docker compose -p rag-updated up -d api ingestion_worker web
```

4. Open `http://localhost:8080/reset-password` locally and reset the intended email.
5. Reapply `demo up -d` and repeat Section 3.4, including the HTTP 403 check, **before** restarting remote access.

This is a local operator procedure, not a public reset mechanism. Do not use this profile-switch procedure on the cloud VM while its public ingress is active. There is currently no dedicated administrator password-reset UI or CLI. A cloud account recovery procedure must be arranged before relying on the site; configuring a suitable email service later is one option. Do not publish the local shortcut to avoid that requirement.

## 9. Back up the demo

Docker volumes survive normal container recreation, but they are not backups. Keep the database and original uploads together. Model weights can be downloaded again if the same versions remain available, but model identity changes can require reindexing.

The following Bash block uses the `demo` function from Section 3. It briefly stops API/worker writes, creates a private archive, and resumes them even if a backup step fails. Run while both services are normally running, with enough free disk. Stop the tunnel or announce maintenance to avoid failed visitor requests.

```bash
(
  set -e
  umask 077
  backup_root="$HOME/atlas-backups"
  mkdir -p "$backup_root"
  chmod 700 "$backup_root"
  backup_dir=$(mktemp -d "$backup_root/backup-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
  trap 'demo start api ingestion_worker >/dev/null' EXIT
  demo stop api ingestion_worker
  demo exec -T postgres pg_dump -U rag -Fc rag > "$backup_dir/database.dump"
  demo run --rm --no-deps --entrypoint tar api \
    -C /app/uploads -czf - . > "$backup_dir/uploads.tar.gz"
  demo exec -T ollama ollama list > "$backup_dir/models.txt"
  demo exec -T postgres pg_restore --list < "$backup_dir/database.dump" >/dev/null
  (
    cd "$backup_dir"
    sha256sum database.dump uploads.tar.gz models.txt > SHA256SUMS
  )
  date -u +%FT%TZ > "$backup_dir/COMPLETED"
  printf 'Backup directory: %s\n' "$backup_dir"
)
```

Copy the exact printed path into this verification command:

```bash
bash deploy/verify-backup.sh "$HOME/atlas-backups/backup-REPLACE-WITH-ACTUAL-DIRECTORY"
```

The existing verification script restores into a disposable network-isolated PostgreSQL container. It checks database restore and upload archive integrity, not a full browser/application restore. It needs Docker access and temporary disk space. A backup without `COMPLETED` is incomplete.

The backup includes document contents and personal data. It is not encrypted by these commands. Encrypt it before copying to an off-machine destination you trust; existing removable storage is an option if you already have it. Keep the environment/secrets separately. A backup only on the same disk does not protect against disk loss.

For a demo, back up after important uploads and before upgrades. Retain a few known-good versions; check disk space before adding more. Do not remove originals until you have successfully verified another copy.

## 10. Back up and restore cloud hosting

### 10.1 Use the included cloud backup scripts

On the VM, from `/home/ubuntu/atlas`:

```bash
sudo bash deploy/backup.sh \
  /home/ubuntu/.config/atlas/production.env \
  /home/ubuntu/atlas-backups
```

Use the exact printed backup directory:

```bash
sudo bash deploy/verify-backup.sh \
  /home/ubuntu/atlas-backups/backup-REPLACE-WITH-ACTUAL-DIRECTORY
```

The backup helper uses the `rag-production` project and the production overlay internally; use it for Route C, not the local demo. Its output is private and normally root-owned when invoked with `sudo`. Arrange a secure encrypted off-VM copy; do not solve transfer permissions by making personal data world-readable.

### 10.2 Rehearse a complete restore on an empty environment

Do not attempt your first restore against the only working deployment. Prepare another empty environment with the matching code, environment secrets and model configuration. The following outline assumes a **new, empty** production project on a replacement machine, with source/images prepared, no active users, and a verified backup accessible at `/private/backup`:

```bash
prod build api ingestion_worker web
prod up -d postgres ollama
prod exec -T postgres pg_isready -U rag -d rag
```

Wait for PostgreSQL readiness, then restore into the new empty `rag` database:

```bash
prod exec -T postgres pg_restore --exit-on-error --no-owner --no-privileges \
  -U rag -d rag < /private/backup/database.dump

prod run --rm --no-deps -T --user root --entrypoint sh api \
  -c 'tar -xzf - -C /app/uploads && chown -R 10001:10001 /app/uploads' \
  < /private/backup/uploads.tar.gz

prod exec ollama ollama pull all-minilm
prod exec ollama ollama pull qwen2.5:3b
prod up -d
```

These restore commands are for a trusted archive and an empty destination. They are not a merge procedure for an existing installation. Preserve the original model identities/digests where possible; generic tags may later resolve to different weights. Pull/recover the recorded versions or deliberately reindex if the embedding identity differs. Check stored file access, counts, account login and known questions. Only then update DNS or allow visitors. Certificate state/model weights are not included in the supplied backup archives.

## 11. Update and restart

### Local demo updates

Stop the tunnel while changing the app. Back up first. In a terminal with the correct `demo` definition and URL:

```bash
demo up -d --build api ingestion_worker web
demo ps
curl --fail http://127.0.0.1:8080/api/ready
curl --fail http://127.0.0.1:8080/api/auth/config
```

Refresh the browser with Ctrl+Shift+R. Restart the tunnel only after configuration and application checks pass. Restarting a Quick Tunnel gives a different URL.

To stop/resume without rebuilding:

```bash
demo stop
demo up -d
```

### Cloud updates

Back up and verify first. Transfer/review the new code or pull the actual committed release, then:

```bash
prod up -d --build api ingestion_worker web
prod ps
prod logs --tail=100 api ingestion_worker
```

The API applies migrations on startup. A new schema migration may prevent simply reverting the image; use a compatible release or a rehearsed full restore when necessary. Keep source versions and model digests with release notes. Do not run `git reset --hard` or overwrite uncommitted work as an update shortcut.

**Never use `docker compose down --volumes` as an upgrade command.** It removes named-volume data. Avoid global `docker system prune --volumes` on this machine. Normal `up -d --build` recreates containers while retaining their volumes.

## 12. Monitor resources and answer quality

For the demo:

```bash
demo ps
demo logs --tail=100 api ingestion_worker
docker stats --no-stream
df -h /
free -h
```

For cloud hosting, use `prod ps`, `prod logs`, `sudo docker stats --no-stream`, `df -h /` and `free -h`. Avoid printing full `docker inspect`, Compose environment output or `.env` files when sharing diagnostics; they can expose secrets.

The readiness endpoint checks the database schema. It explicitly says inference is checked on use. Confirm real inference with a representative document upload and question after model changes, upgrades or restores. Unit tests use mocked providers and cannot establish model speed or answer quality on a new host.

Keep a small set of test questions with known answers, including personal-document questions, wrong-person questions, file-specific questions and questions whose answers are absent. Review citations for complete readable passages and correct document/page links. Track slow questions and failed indexing before increasing the audience.

The demo overlay rotates Docker logs. The production profile currently needs host-level log rotation configured separately. If Docker already has a `daemon.json`, merge a `json-file` rotation configuration into it rather than overwriting other settings; follow Docker's documentation and restart/recreate affected services during maintenance. Logs alone are not a compliance audit trail.

## 13. Troubleshoot

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Port 8080/8001 already allocated | Another Compose project or local process owns it | Inspect `docker ps` and `docker compose -p rag-updated ps`; use the intended existing project. Do not stop unrelated containers blindly. |
| Documents disappeared after deployment | Different project/host has fresh volumes | Confirm project name and machine. Do not initialize over, delete or rename the old volumes. |
| Direct reset still visible remotely | Local profile applied, old API configuration, or cached UI | Stop exposure immediately; apply demo/production profile and check both configuration flags plus endpoint HTTP 403. Refresh the UI. |
| Signup disappeared | Sharing profiles deliberately disable public registration | Sign in with the existing administrator; create members through Members. |
| Forgot password says email is not configured | Direct reset is disabled and SMTP is empty | Expected remotely with no SMTP; use the controlled local recovery process only after stopping exposure. |
| Tunnel hostname no longer works | Tunnel stopped, recreated, or host slept | Start a new tunnel, use its new URL and update `DEMO_PUBLIC_APP_URL`. |
| `--allowed-mail` is not recognized | Old cloudflared version | Update using the official repository; confirm support before sharing the link. |
| Public tunnel works but local `/api/ready` fails | App/database startup or migration issue | Fix local health first; inspect API and database logs. |
| HTTPS page loads but API returns 502 | Nginx cannot reach API, or upstream changed after recreation | Check API health; inspect `demo logs web api` or `prod logs web api`. If API was recreated alone, restart `web` and retry. |
| Upload remains queued | Worker stopped, waiting on API, or processing another file | Check worker logs, API health and CPU/RAM; keep one small upload in flight initially. |
| Provider/model unavailable or HTTP 503 | Missing Ollama model or provider not reachable | Check `exec ollama ollama list`, pull required models and inspect Ollama logs. |
| PDF has no usable text | Scanned/image-only PDF or unsupported extraction | Try a text-based PDF/TXT. OCR is not implemented in the current pipeline. |
| Question times out | CPU inference, excessive context, competing jobs, or proxy timeout | Inspect utilization; reduce simultaneous work and test a smaller document. Raising a timeout alone does not add capacity. |
| `!reset` parse error | Old Compose plugin | Upgrade to a compatible current Compose plugin; use `docker compose`, not obsolete `docker-compose`. |
| Docker socket permission denied | User cannot access the daemon | On the VM, use `sudo` as documented. Do not make the socket world-writable. |
| Cloud VM unavailable to provision | Free shape lacks capacity | Use Route A/B or try again later within provider rules; do not purchase another shape accidentally. |
| VM build fails on ARM | Image/dependency architecture mismatch | Inspect the specific build error; do not assume AMD64 artifacts run natively on ARM. |
| Caddy cannot obtain certificate | DNS, blocked 80/443, wrong hostname, or certificate rate limit | Check DNS, cloud/host firewall and Caddy logs. Do not repeatedly recreate certificate storage. |
| HTTP 429 for several testers | Authentication/chat ingress rate limit, possibly shared proxy IP | Wait; review actual trusted forwarding/IP behavior before tuning limits. Do not disable throttling globally. |
| Database authentication fails after changing `.env` | Existing database was initialized with an earlier password | Restore the matching environment secret. Changing the Compose value does not change a stored PostgreSQL password. |

## 14. Cost controls and completion checklist

### Expected added spending

| Item | Routes A/B | Route C |
| --- | --- | --- |
| Compute | Existing computer; electricity/internet remain your responsibility | Eligible free VM only, within current account limits |
| Address | Provider HTTPS hostname | Free Duck DNS subdomain |
| AI requests | Local Ollama, no paid API configured | Ollama on the VM, no paid API configured |
| Database/uploads | Existing disk; provide your own backups | VM disk within allowance; keep an off-VM backup |
| Availability | Depends on your computer and network | Depends on provider capacity, account status and your operations |
| Password email | Not required for local direct reset; disabled when shared | Unavailable without SMTP or another implemented recovery mechanism |

Do not enable paid upgrades to solve capacity shortages if your budget is strictly zero. Do not rely on temporary credits as a permanent free plan. Check usage and storage regularly, and remove unused cloud resources after preserving necessary backups. A budget alert does not automatically prevent charges. Keep records of which resources the console marks free.

### Before sharing the address

- The correct Compose project and overlay are in use.
- Direct password reset and public signup are both disabled server-side.
- You can sign in as administrator, and testers have separate member accounts.
- No original private employee documents are accidentally exposed to demo users.
- Real upload, indexing, file-specific chat and citations have been checked.
- Two-account access isolation has been tested.
- Required models are installed and performance is acceptable for one user first.
- A database-plus-uploads backup has been verified and stored separately.
- Visitors understand when the demo will be available and how to report problems.
- You know how to stop the tunnel or shut down access immediately.

### What this guide prepares and what it does not launch

The guide and `compose.demo.yaml` prepare a repeatable deployment path. They do not create provider accounts, accept payment terms, install cloudflared/Tailscale, provision a VM, change DNS, start a public tunnel or expose the current app automatically. Run the chosen route deliberately when ready. Cloud and tunnel behavior must be verified on the actual host; passing local tests and Compose validation is not a completed internet deployment.
