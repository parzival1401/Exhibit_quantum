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

## Moving to the museum's account

Repeat steps 1–4 in the museum's account, then change `AWS_BUCKET` (and
`AWS_REGION` if theirs differs) in `main.py` and the keys in the credentials
file. Afterwards, delete the test access key in the test account (IAM →
user → Security credentials → Delete).

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
