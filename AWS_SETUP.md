# Sending the QR code through Amazon S3

By default the QR code from **FINISH** points at a small web server on the
exhibit computer, so a visitor's phone must be on the same Wi-Fi. With an S3
bucket configured, FINISH also uploads the artwork to Amazon S3 and the QR
code carries a temporary download link that works on any connection,
mobile data included. If the upload fails (no internet, wrong keys), the
exhibit falls back to the Wi-Fi QR code on its own.

What lives where:

| Piece | Where |
| ----- | ----- |
| Upload code | `cloud_upload.py`, called from `_finish()` in `window2_image.py` |
| Settings | top of `main.py`: `AWS_BUCKET`, `AWS_REGION`, `AWS_PROFILE`, `AWS_LINK_DAYS` |
| Keys | the exhibit computer's AWS credentials file — **never in this repo** |
| Python library | `boto3` (in `requirements.txt`) |

The design: the bucket stays **private**. Each upload goes to
`artwork/<file name>` and the QR code holds a **presigned link** that
expires after `AWS_LINK_DAYS` (7 at most — the limit for links signed
with an IAM user's keys). A lifecycle rule deletes uploads after 30 days.

## One-time setup in an AWS account

Do this once per account (your test account now, the museum's account
later). Names below are suggestions; anything works if `main.py` matches.

### 1. Create the bucket

1. AWS console → **S3** → **Create bucket**.
2. **Region:** the account's region (ours: `us-east-2`, Ohio).
3. **Bucket name:** globally unique, lowercase, e.g.
   `exhibit-quantum-artwork-<something-unique>`.
4. Leave **Block all public access** turned **on** (the default).
5. **Create bucket**.

### 2. Auto-delete uploads after 30 days

1. Open the bucket → **Management** → **Create lifecycle rule**.
2. Name: `delete-artwork-after-30-days`.
3. Scope: **Limit the scope using filters** → prefix `artwork/`.
4. Rule actions: tick **Expire current versions of objects**.
5. Days after object creation: `30` → **Create rule**.

### 3. Create an upload-only user for the exhibit computer

1. AWS console → **IAM** → **Policies** → **Create policy** → **JSON**.
2. Paste this, replacing `BUCKET-NAME` (twice) with your bucket's name:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "ExhibitArtworkUploadAndLink",
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject"],
         "Resource": "arn:aws:s3:::BUCKET-NAME/artwork/*"
       }
     ]
   }
   ```

   `PutObject` uploads the drawing; `GetObject` is what the presigned link
   borrows to let the phone download it. Nothing else in the account is
   reachable with these keys.
3. Name it `ExhibitQuantumArtworkUpload` → **Create policy**.
4. **IAM** → **Users** → **Create user** → name `exhibit-quantum-uploader`.
   Do **not** give it console access.
5. **Attach policies directly** → tick `ExhibitQuantumArtworkUpload` →
   **Create user**.
6. Open the user → **Security credentials** → **Create access key** →
   use case **Application running outside AWS** → **Create**.
7. Copy the **Access key ID** and **Secret access key**. The secret is
   shown only once.

### 4. Put the keys on the exhibit computer

Create (or add to) the AWS credentials file:

- macOS / Linux: `~/.aws/credentials`
- Windows: `C:\Users\<you>\.aws\credentials`

```ini
[exhibit-quantum]
aws_access_key_id = AKIA................
aws_secret_access_key = ........................................
```

The `[exhibit-quantum]` name must match `AWS_PROFILE` in `main.py`.

### 5. Turn it on

In `main.py`:

```python
AWS_BUCKET    = 'exhibit-quantum-artwork-<something-unique>'
AWS_REGION    = 'us-east-2'
```

Install the library once: `pip install -r requirements.txt`.

### 6. Test

Run the exhibit, colour a drawing, press **FINISH**. The status line reads
"uploaded" when the cloud link is used. Turn the phone's **Wi-Fi off** and
scan — if the image opens over mobile data, it is coming from S3. If the
status says "upload failed, Wi-Fi link", the terminal prints the reason
(`[Cloud] Upload failed …`).

## The current setup: a test account (concept run)

Everything is presently wired to a **free test account** with no billing
information, set up on 2026-11-04 and verified end to end — a phone with
Wi-Fi off downloaded its drawing from S3.

| Piece | Value in the test account |
| ----- | ------------------------- |
| Account ID | `332778515287` |
| Region | `us-east-2` (Ohio) |
| Bucket | `exhibit-quantum-artwork-332778515287` — private, 30-day delete rule `delete-artwork-after-30-days` on `artwork/` |
| IAM policy | `ExhibitQuantumArtworkUpload` — `s3:PutObject` + `s3:GetObject` on `artwork/*` only |
| IAM user | `exhibit-quantum-uploader` — no console access, that policy only |
| Exhibit keys | `~/.aws/credentials` profile `[exhibit-quantum]` on the development Mac |
| Admin sign-in | profile `exhibit-dev` (`aws login`), used only to create the above |
| `main.py` | `AWS_BUCKET = 'exhibit-quantum-artwork-332778515287'`, `AWS_REGION = 'us-east-2'`, `AWS_PROFILE = 'exhibit-quantum'` |

Verified on the test account: upload and presigned download (200,
`image/png`), a 361-character link (QR version 14), and the upload key
**refused** for listing the bucket, writing outside `artwork/`, deleting,
and listing buckets.

## Switching to the museum's (real) account

The code does not change — only the account-specific values do. Work
through this list in order.

**In the museum's AWS account** (steps 1–3 above, or the CLI commands in
the next section):

- [ ] Note the account's **region**.
- [ ] Create the bucket, e.g. `exhibit-quantum-artwork-<museum account ID>`
      (bucket names are global, so the test bucket's name is taken).
      Keep **Block all public access** on.
- [ ] Add the 30-day delete rule on `artwork/` (or whatever retention the
      museum wants — ask; it is their visitors' data).
- [ ] Create the policy with the **new bucket name** in its `Resource`.
- [ ] Create the upload user, attach the policy, create its access key.

**On the exhibit computer:**

- [ ] Python dependencies: `pip install -r requirements.txt` (includes
      `boto3`).
- [ ] Credentials file (step 4 above) with the museum's key under
      `[exhibit-quantum]`. If this computer still has the test key under
      that name, replace both lines.
- [ ] In `main.py`, change `AWS_BUCKET` to the new bucket, and
      `AWS_REGION` if the museum's region is not `us-east-2`. Leave
      `AWS_PROFILE` as `exhibit-quantum` (or change both it and the
      `[…]` name in the credentials file to match).
- [ ] Check the clock syncs automatically.
- [ ] Test (step 6): **FINISH**, status says "uploaded", phone with Wi-Fi
      off opens the drawing. Test once **on the museum's network** too —
      some venue networks block uploads.

**Then retire the test account:**

- [ ] Delete the test key: IAM → Users → `exhibit-quantum-uploader` →
      Security credentials → Deactivate → Delete. (Or delete the user, the
      policy and the bucket outright.)
- [ ] Remove the `[exhibit-quantum]` test lines from any computer that
      still has them, and `[profile exhibit-dev]` from `~/.aws/config` once
      the admin sign-in is no longer needed.

If an upload fails at any point, the exhibit keeps working on the Wi-Fi
QR code and the terminal prints `[Cloud] Upload failed …` with the AWS
reason — start there.

## The same setup from the command line

This is how the test account was set up, with the AWS CLI v2 and an admin
sign-in (`aws login --region <region> --profile <admin-profile>`). Replace
`BUCKET`, `REGION` and `ADMIN` with the museum's values. The key in the last
step goes straight into the credentials file without being printed.

```bash
export AWS_PROFILE=ADMIN

aws s3api create-bucket --bucket BUCKET --region REGION \
  --create-bucket-configuration LocationConstraint=REGION
# (omit --create-bucket-configuration when REGION is us-east-1)

aws s3api put-bucket-lifecycle-configuration --bucket BUCKET \
  --lifecycle-configuration '{"Rules":[{"ID":"delete-artwork-after-30-days","Status":"Enabled","Filter":{"Prefix":"artwork/"},"Expiration":{"Days":30}}]}'

POL=$(aws iam create-policy --policy-name ExhibitQuantumArtworkUpload \
  --query Policy.Arn --output text --policy-document \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:PutObject","s3:GetObject"],"Resource":"arn:aws:s3:::BUCKET/artwork/*"}]}')
aws iam create-user --user-name exhibit-quantum-uploader
aws iam attach-user-policy --user-name exhibit-quantum-uploader --policy-arn "$POL"

read -r KID SECRET <<< "$(aws iam create-access-key --user-name exhibit-quantum-uploader \
  --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text)"
AWS_PROFILE= aws configure set aws_access_key_id "$KID" --profile exhibit-quantum
AWS_PROFILE= aws configure set aws_secret_access_key "$SECRET" --profile exhibit-quantum
AWS_PROFILE= aws configure set region REGION --profile exhibit-quantum
unset SECRET
```

Using the admin sign-in profile from Python (e.g. for a quick test) needs
`pip install "botocore[crt]"`; the exhibit itself uses plain access keys and
does not. Never point `AWS_PROFILE` in `main.py` at the admin sign-in: its
links are too long for a QR code (see below).

## Things to know

- The exhibit computer needs internet; the phone no longer needs the
  exhibit's Wi-Fi. Check early that the venue's network allows uploads.
- The computer's clock must be right — AWS rejects requests and links
  signed by a clock far off. Automatic time sync is enough.
- Cost is effectively zero: a drawing is ~30 KB.
- A presigned link from the upload user's keys is ~380 characters, which
  makes a comfortably scannable QR code (version 15, ~4.4 px per module in
  the dialog). Use those keys, not an `aws login` / SSO profile: temporary
  credentials add a session token that makes the link ~2,500 characters,
  too long for a QR code — the exhibit then falls back to Wi-Fi and the
  terminal says why.
