# Xenage Landing

Next.js one-page landing for `xenage.dev` focused on agent orchestration and control-plane UX.

## Local

```bash
cd landing
npm install
npm run dev
```

## Docker

```bash
cd landing
docker build -t xenage-landing .
docker run --rm -p 3000:3000 xenage-landing
```

Open http://localhost:3000
