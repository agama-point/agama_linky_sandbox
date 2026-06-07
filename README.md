# Agama Linky Sandbox

This directory is a local test and learning sandbox for experimenting with the
Linky project, key derivation, local tooling, and helper scripts.

It is not production infrastructure, not a secure wallet environment, and not a
recommended model for handling real secrets.

## Warning

The files in this directory may contain generated test seeds, derived private
keys, Cashu wallet material, Evolu owner mnemonics, Nostr `nsec` values, and
other sensitive data.

This is deliberately a verbose educational setup. It is useful for learning how
Linky derives keys, but this is absolutely not how production keys should be
handled.

Do not use this directory for real funds, real accounts, or real identities.
Do not commit `.env`, `linky_keys.txt`, or any generated key export. Do not paste
those files into chat systems, issue trackers, logs, screenshots, or cloud sync
folders.

## You Must Know What You Are Doing

If you run the helper scripts here, assume the output is sensitive. In
particular:

- A SLIP-39 share can recover the Linky master secret.
- A Nostr `nsec` controls the Nostr identity.
- Cashu seed material can affect wallet recovery and token handling.
- Evolu owner mnemonics and owner IDs are part of local-first sync identity.
- Cashu token strings may contain spendable proof material.

If any of this is unclear, stop and treat the files as compromised test data
only.

## Documentation

- [INSTALL_BUN.md](INSTALL_BUN.md) describes the portable Windows Bun/Node setup
  used for this sandbox, including cache locations, local-only constraints, and
  the practical issues encountered while starting Linky locally.
- [LINKY_KEYS.md](LINKY_KEYS.md) maps Linky's key material: SLIP-39 master
  share, derived Nostr keys, Cashu wallet seed, Evolu owner lanes, derivation
  paths, and what is stored locally or in Evolu.

## Files

- `.env` may contain `LINKY_MASTER_MNEMO`, a test-only 20-word SLIP-39 share.
- `linky_keys.py` derives Linky-related keys from that test seed.
- `linky_keys.txt` is the generated export and contains secret material.
- `linky-main/` is the Linky application checkout/workspace.

## Planned Python Test Fragments

These are planned small Python-oriented experiments, not production clients:

- [agama-point/py_nostr](https://github.com/agama-point/py_nostr) - Nostr key, event, relay, and message-flow experiments.
- [octopusengine/py_evolu](https://github.com/octopusengine/py_evolu) - Evolu owner/key/sync-model exploration and local data inspection.
- [agama-point/py_cashu](https://github.com/agama-point/py_cashu) - Cashu mint, token, deterministic seed, and wallet-flow experiments.

## Intended Use

This sandbox is for local education and debugging only:

1. Generate or place a test-only `LINKY_MASTER_MNEMO` in `.env`.
2. Run `linky_keys.py` to inspect how Linky derives keys.
3. Read the generated `linky_keys.txt` locally.
4. Delete or rotate test data whenever it is no longer needed.

For real systems, use proper secret storage, minimize key exposure, avoid
terminal/log dumps, and follow the security model of the production platform.