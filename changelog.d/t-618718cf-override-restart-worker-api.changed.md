- Docs: after changing `WHO2BE_ROUTINE_*` or `WHO2BE_WORKER_ENABLED`, the
  RUNBOOK and the cloud first-run guide now say to recreate both `worker` and
  `api` (`$COMPOSE up -d worker api`, a redeploy on Dokploy). The `api` reads the
  same variables for the operator view `GET /v1/system/routines`; restarting
  only `worker` left that view showing the old schedules.
