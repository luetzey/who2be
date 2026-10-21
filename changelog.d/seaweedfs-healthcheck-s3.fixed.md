- Deploy: The SeaweedFS healthcheck now also requires an answer from the S3
  port (8333, any HTTP status counts, including 403), with a 60 s
  `start_period`. Before, only the master port was checked; after the update to
  SeaweedFS 4.48 the master was healthy before the S3 gateway listened, and
  `blobstore-bootstrap` failed with `Connection refused`, which kept `api` from
  starting. In addition, `blobstore-bootstrap` retries the first contact on
  connection errors with backoff for about 60 s and then exits with a clear
  message. SeaweedFS stays on 4.48.
