"""
cloud_upload.py — Upload finished artwork to Amazon S3 for the QR code.

The Wi-Fi QR code only works for phones on the exhibit's own network.
With a bucket configured in main.py, Finish uploads the artwork to S3
and the QR code carries a presigned link instead: the object stays
private, but anyone holding the link can download it, over any
connection, until the link expires.

Credentials are never kept in this repo. boto3 reads them from a named
profile in the AWS credentials file — ~/.aws/credentials on macOS and
Linux, %USERPROFILE%\\.aws\\credentials on Windows. See AWS_SETUP.md.

boto3 is imported inside the function, so the exhibit still starts on a
machine without it and simply keeps the Wi-Fi QR code.
"""

# A presigned link signed with an IAM user's keys cannot outlive 7 days.
MAX_LINK_SECONDS = 7 * 24 * 3600

# Longest link worth putting in the dialog's QR code: past this the code
# gets too dense to scan reliably at its on-screen size.
MAX_QR_LINK = 1000

# Every upload goes under this prefix. The IAM policy and the bucket's
# auto-delete rule are both scoped to it (see AWS_SETUP.md).
KEY_PREFIX = 'artwork/'


def upload_artwork(path: str, fname: str, bucket: str, region: str,
                   profile: str, link_days: float) -> str:
    """Upload `path` as KEY_PREFIX + fname and return a presigned download link.

    Raises on any failure (no boto3, missing profile, no network, access
    denied); the caller falls back to the Wi-Fi link.
    """
    import boto3
    from botocore.config import Config

    session = boto3.Session(profile_name=profile or None, region_name=region)
    # The regional endpoint, explicitly: left to itself boto3 builds the
    # presigned link on the global s3.amazonaws.com host while signing it
    # for `region`, and S3 rejects that pair for any bucket outside
    # us-east-1 ("the region 'us-east-2' is wrong").
    s3 = session.client('s3', endpoint_url=f'https://s3.{region}.amazonaws.com',
                        config=Config(
        signature_version='s3v4',
        connect_timeout=5,
        read_timeout=10,
        retries={'max_attempts': 2},
    ))

    key = KEY_PREFIX + fname
    # ContentType, so a phone shows the image instead of downloading an
    # unnamed file.
    s3.upload_file(path, bucket, key, ExtraArgs={'ContentType': 'image/png'})

    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=min(int(link_days * 24 * 3600), MAX_LINK_SECONDS),
    )
    # An IAM user's keys give a ~350-character link. Temporary credentials
    # (an `aws login` or SSO profile) add a session token that pushes it
    # past 2,500 — more than any QR code holds.
    if len(url) > MAX_QR_LINK:
        raise ValueError(
            f'link is {len(url)} characters, too long for a QR code — '
            f'profile {profile!r} has temporary credentials; use the '
            f'upload user\'s access keys (AWS_SETUP.md, step 4)'
        )
    return url
