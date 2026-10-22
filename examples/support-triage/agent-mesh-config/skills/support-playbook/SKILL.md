---
# Copyright Solace Corporation
# SPDX-License-Identifier: Apache-2.0
name: support-playbook
description: The support team's rules for the first reply to a customer, plus its knowledge-base articles. Load it before drafting or reviewing any reply to a customer issue.
tags: [support, customer-replies]
---

# Support playbook

Follow these rules for every first reply to a customer.

## Before you write

1. Search the knowledge base for the customer's problem with
   `grep_skill_resources` (try two or three key words from the issue, such as
   `invoice`, `CSV`, `charge`, `503`, `password`), then read any article that
   matches with `read_skill_resource`. Articles are under `references/kb/`.
2. If an article matches, the reply must use it: give its steps or its policy
   in your own words. If no article matches, do not invent product steps,
   menus or policies.

## What every reply contains

- One sentence that restates the problem in the customer's own terms.
- When they will hear from us next, as one sentence such as "We will get back
  to you by <deadline>." The deadline is our commitment to the customer, never
  a deadline for the customer. Copy it exactly as you were given it; if you
  were given none, say the team will follow up shortly. Never work out a
  deadline yourself, and never promise a fix time or a root cause.
- The answer, if a knowledge-base article covers it.
- Every item from the triage's missing information, as a numbered list. Skip
  this list if there is nothing missing.
- The sign-off "The Support Team". No subject line.

## Rules by category

- **Outage:** apologise once, point to the status page in
  `references/kb/service-status.md`, and say updates follow there.
- **Billing:** never ask for a full card number, password or bank details.
  Follow `references/kb/duplicate-charges.md` for duplicate charges.
- **Account access:** never ask for a password. Follow
  `references/kb/password-reset.md`.
- **How-to:** if an article answers the question, the reply is the answer.
  Keep it to the steps the article gives.

## Tone

Plain, warm and short: at most 150 words before the numbered list. No
exclamation marks, no "we apologise for any inconvenience", no internal
team names, priorities or severity labels.
