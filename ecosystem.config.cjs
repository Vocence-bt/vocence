/**
 * PM2 ecosystem config for Vocence validator (two processes).
 *
 * Usage (from repo root):
 *   pm2 start ecosystem.config.cjs
 *
 * Ensure .env is configured and uv is installed (uv sync).
 * Logging: LOG_LEVEL=INFO so all logs are visible in pm2 logs.
 */
module.exports = {
  apps: [
    {
      name: "vocence-generator",
      script: "uv",
      args: "run vocence services generator",
      cwd: __dirname,
      interpreter: "none",
      autorestart: true,
      watch: false,
      env: { LOG_LEVEL: "INFO" },
    },
    {
      name: "vocence-validator",
      script: "uv",
      args: "run vocence services validator",
      cwd: __dirname,
      interpreter: "none",
      autorestart: true,
      watch: false,
      env: { LOG_LEVEL: "INFO" },
    },
  ],
};
