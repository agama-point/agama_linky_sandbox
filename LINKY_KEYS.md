# Linky Keys

This document describes how Linky handles user secrets, derived keys, and
Evolu owners. It is based on the current TypeScript implementation in
`packages/core/src/identity/` and `apps/web-app/src/`.

## Short Version

Linky has one human backup secret for seed-based accounts:

```text
20-word SLIP-39 share
```

That SLIP-39 share recovers a binary master secret. Linky derives all normal
seed-login identities from that master secret:

- Nostr signing key (`nsec` / `npub`)
- Cashu deterministic wallet seed
- Evolu owner keys for synced local-first data lanes

The app also supports a temporary custom Nostr `nsec` override during a
SLIP-39 session. In that mode, contacts, Cashu, messages, transactions, and
Evolu owners still come from the SLIP-39 seed; only the active Nostr identity
is replaced.

## Main Terms

### SLIP-39 Share

The user-facing backup phrase is a normalized 20-word SLIP-39 share.

Linky creates it with:

- 16 bytes of random entropy
- group threshold `1`
- one group with one required share
- empty passphrase by default
- title `Linky`

The share is validated with `slip39-ts`.

### Master Secret

The SLIP-39 share is recovered into a binary `MasterSecret`.

Current type constraints:

```text
MasterSecret = Uint8Array, 16 to 64 bytes
```

This master secret is not the same thing as a BIP-39 mnemonic. It is the root
binary secret used as the input to `HDKey.fromMasterSeed`.

### BIP-39 Mnemonics

Linky uses BIP-39 mnemonics internally for two purposes:

- a 24-word Cashu mnemonic derived from the SLIP-39 master secret
- 12-word Evolu owner mnemonics derived from the SLIP-39 master secret

These are deterministic implementation details, not additional user backup
phrases.

## Derivation Rules

The root is:

```text
root = HDKey.fromMasterSeed(masterSecret)
```

For BIP-85-style outputs, Linky derives an HD private key at a path and then
computes:

```text
hmac_sha512("bip-entropy-from-k", derivedPrivateKey).slice(0, bytes)
```

Owner keys use 16 bytes of entropy. The Cashu mnemonic uses 32 bytes.

## Derivation Paths

| Purpose | Path | Output |
| --- | --- | --- |
| Nostr identity | `m/44'/1237'/0'/0/0` | 32-byte Nostr private key, then public key |
| Cashu wallet mnemonic | `m/83696968'/39'/0'/24'/0'` | 32 bytes entropy -> 24-word BIP-39 mnemonic -> 64-byte seed |
| Evolu meta owner | `m/83696968'/39'/0'/24'/1'/0'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |
| Evolu contacts owner lane `n` | `m/83696968'/39'/0'/24'/2'/n'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |
| Evolu Cashu owner lane `n` | `m/83696968'/39'/0'/24'/3'/n'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |
| Evolu messages owner lane `n` | `m/83696968'/39'/0'/24'/4'/n'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |
| Evolu transactions owner lane `n` | `m/83696968'/39'/0'/24'/5'/n'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |
| Evolu identity owner | `m/83696968'/39'/0'/24'/6'/0'` | 16 bytes entropy -> 12-word BIP-39 mnemonic -> Evolu owner |

Owner lane indexes are non-negative integers.

## Nostr Keys

Default seed-login Nostr identity:

```text
private key = root.derive("m/44'/1237'/0'/0/0").privateKey
nsec        = nip19.nsecEncode(private key)
public key  = nostr-tools getPublicKey(private key)
npub        = nip19.npubEncode(public key)
```

The active `nsec` is stored locally through the identity secret storage adapter
under:

```text
linky.nostr_nsec
```

The active Nostr identity can also be synced through Evolu in the
`nostrIdentity` table under the deterministic identity owner. That row stores:

- `nsec`
- `npub`
- `source`: `derived` or `custom`
- `switchedAtSec`: used when a custom identity is activated

Important: this means the active Nostr secret can be present in Evolu data for
seed logins. Treat Evolu storage and sync servers as carrying encrypted/local-
first application data, but do not treat the `nostrIdentity` row as public.

## Cashu Keys

Cashu uses a deterministic BIP-85-derived mnemonic:

```text
entropy32 = BIP85(root, "m/83696968'/39'/0'/24'/0'", 32 bytes)
cashuMnemonic = BIP39 entropyToMnemonic(entropy32)
cashuSeed = mnemonicToSeedSync(cashuMnemonic)
```

Current type constraints:

```text
cashuMnemonic = valid 24-word BIP-39 mnemonic
cashuSeed     = Uint8Array, 64 bytes
```

The Cashu mnemonic is stored locally through the identity secret storage
adapter under:

```text
linky.cashu_bip85_mnemonic
```

Cashu deterministic counters and restore cursors are local-only and bound to
the active Cashu mnemonic:

```text
linky.cashu.detCounter.v1:...
linky.cashu.restoreCursor.v1:...
linky.cashu.detCounterLock.v1:...
```

When the Cashu mnemonic changes, Linky wipes those seed-bound counters because
old counters would point into the wrong deterministic derivation tree.

## Evolu Owners

Evolu writes are scoped by owners. Linky derives deterministic owner mnemonics
from the SLIP-39 master secret and then converts them through Evolu:

```text
ownerMnemonic = BIP39 entropyToMnemonic(ownerEntropy16)
ownerSecret   = Evolu.mnemonicToOwnerSecret(ownerMnemonic)
appOwner      = Evolu.createAppOwner(ownerSecret)
ownerId       = appOwner.id
```

For seed logins, Linky subscribes several owners:

- meta owner
- identity owner
- active contacts owner
- active Cashu owner
- active messages owner
- active transactions owner

Historical lane owners remain visible for reads up to the active index.

For non-seed or legacy sessions, Linky can fall back to a single Evolu app
owner based on `linky.initialMnemonic`.

## Evolu Owner Lanes

The owner lanes split data by domain:

| Evolu table | Owner |
| --- | --- |
| `ownerMeta` | meta owner |
| `nostrIdentity` | identity owner |
| `contact` | contacts owner lane |
| `cashuToken` | Cashu owner lane |
| `nostrMessage` | messages owner lane |
| `nostrReaction` | messages owner lane |
| `transaction` | transactions owner lane |

Contacts, Cashu, messages, and transactions can rotate independently to lane
`n + 1`. Rotations are pointer-only: old lanes stay readable, new writes go to
the newest lane.

Current rotation thresholds:

```text
contacts      220 writes, or 100 contacts per active owner
cashu         170 writes
messages      160 writes
transactions  220 writes
cooldown      60 seconds
```

The active lane pointers are mirrored in `ownerMeta` as rotation snapshots for:

```text
contacts
cashu
messages
transactions
```

The local browser also stores cached indexes and rotation metadata under
`linky.evolu.*` keys.

## What Is Stored in Evolu

Current app schema:

### `contact`

Stores contact profile data:

- name
- `npub`
- Lightning address
- group name
- archived timestamp

### `nostrIdentity`

Stores active Nostr identity state:

- `nsec`
- `npub`
- `source`
- `switchedAtSec`

### `nostrMessage`

Stores decrypted chat messages and metadata:

- contact/thread id
- direction
- plaintext content
- gift-wrap id
- rumor id
- sender pubkey
- timestamps
- client id/status
- reply/edit metadata

### `nostrReaction`

Stores message reactions:

- target message id
- reactor pubkey
- emoji
- timestamp
- wrap id
- client id/status

### `cashuToken`

Stores wallet token rows:

- current token string
- optional raw pasted token
- mint
- unit
- amount
- state
- error

Cashu token strings can contain spendable token material. Treat this table as
sensitive wallet data.

### `transaction`

Stores payment history:

- timestamp
- direction/status
- amount/fee
- category/method/phase
- note/details
- icon kind
- optional contact id
- mint/unit/error/pending label

### `ownerMeta`

Stores synced owner-lane metadata such as active lane snapshots and shared
settings like the selected default mint.

## What Is Stored Locally

Identity secrets are persisted through `platform/secretStorage.ts`.

On web, the fallback is `localStorage`.

On native platforms:

- Android uses `LinkyNativeSecretStorage`, backed by native secure storage.
- iOS uses the `LinkySecretStorage` Capacitor plugin when available.
- The web fallback may still be mirrored for compatibility in some native
  paths.

Important local secret keys:

```text
linky.initialMnemonic
linky.nostr_nsec
linky.nostr_slip39_seed
linky.cashu_bip85_mnemonic
linky.nostr_identity_source.v1
linky.nostr_identity_switched_at_sec.v1
```

Push also stores a copy of the active `nsec` in IndexedDB:

```text
database: linky-push-secrets-v1
store:    kv
key:      nostr_nsec
```

That is used by the service worker/client push flows.

## Login Modes

### Seed Login

The normal current account model:

1. User provides or creates a 20-word SLIP-39 share.
2. Linky recovers the master secret.
3. Linky derives Nostr keys, Cashu mnemonic, and Evolu owner mnemonics.
4. Linky stores local secrets through the secret storage adapter.
5. Linky writes synced data to deterministic Evolu owners.

### Custom Nostr Identity

During a seed-login session, the user can paste a custom `nsec`.

In that case:

- Nostr signing uses the custom `nsec`.
- contacts/Cashu/messages/transactions owners still derive from SLIP-39.
- `nostrIdentity.source` becomes `custom`.
- `switchedAtSec` is set so older incoming events can be ignored.
- The user can restore the derived Nostr identity later.

## Security Notes

- Never commit real SLIP-39 shares, BIP-39 mnemonics, `nsec` values, Cashu
  mnemonics, or Cashu tokens.
- `.env` files and local storage exports may contain real mnemonic material.
- Cashu token rows are wallet-sensitive because token strings may contain
  spendable proof material.
- Nostr `nsec` is both a signing key and an account-control secret.
- Evolu owner mnemonics are deterministic from the SLIP-39 master secret; they
  should be treated as secrets even though users normally never see them.

