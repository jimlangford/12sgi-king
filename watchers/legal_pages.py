#!/usr/bin/env python3
"""legal_pages.py — the commerce/consumer-protection legal pages required before charging live
   (Jimmy 2026-06-18: "use standard approved attorney documents that cover"). Generates, into
   reports/mauios/ (PUBLIC build), three standard documents tailored to the civic platform:
     terms.html     — Terms of Service (incl. subscriptions + ROSCA auto-renewal + arbitration + civic-data disclaimer)
     privacy.html   — Privacy Policy (Stripe + Stripe Identity gov-ID handling + CCPA/CPRA + GDPR + cookies + rights)
     refunds.html   — Billing, Auto-Renewal, Cancellation & Refund Policy (ROSCA-compliant)

These are built on the STANDARD provisions a SaaS subscription business must publish for FTC/ROSCA
and Stripe merchant requirements. They are complete and standard-grade; a licensed attorney should do
a final pass for the specific entity + jurisdiction before reliance (noted to the owner, not on-page).

Business facts pulled from config/legal.json (entity name, contact, governing law) so they are not
hard-coded; edit that file to finalize the legal entity + address before go-live.
"""
import os, json, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
HST     = timezone(timedelta(hours=-10))
esc = lambda s: html.escape(str(s or ""))

DEFAULTS = {
    "entity": "12 Stones Global",
    "dba": "Kilo Aupuni / govOS",
    "contact_email": "jimlangford@me.com",
    "jurisdiction": "State of Hawaiʻi",
    "venue": "the state and federal courts located in Maui County, Hawaiʻi",
    "address": "[business mailing address — confirm before go-live]",
    "effective": None,   # filled with today if None
}
def cfg():
    c = dict(DEFAULTS)
    try: c.update(json.load(open(os.path.join(PROJECT, "config", "legal.json"), encoding="utf-8")))
    except Exception: pass
    if not c.get("effective"): c["effective"] = datetime.now(HST).strftime("%B %-d, %Y") if os.name != "nt" else datetime.now(HST).strftime("%B %d, %Y")
    if str(c.get("address", "")).startswith("["): c["address"] = ""   # don't ship a placeholder address publicly
    return c

def page(title, body, c):
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>%s — %s</title>
<style>
 body{margin:0;background:#fff;color:#13243d;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;line-height:1.65;font-size:15px}
 .wrap{max-width:820px;margin:0 auto;padding:26px 20px 70px}
 h1{font-size:26px;color:#00356b;margin:.2em 0 .1em} h2{font-size:18px;color:#00356b;margin:1.5em 0 .3em}
 h3{font-size:15px;margin:1.1em 0 .2em} .eff{color:#5a6b7b;font-size:13px;margin-bottom:1.2em}
 p,li{color:#22364f} a{color:#1259a3} .box{background:#f3f7fc;border:1px solid #cfe0f2;border-radius:9px;padding:12px 16px;margin:14px 0;font-size:14px}
 .nav{font-size:13px;color:#5a6b7b;margin-bottom:14px} .nav a{margin-right:12px}
 footer{margin-top:30px;border-top:1px solid #e3e9f1;padding-top:12px;color:#5a6b7b;font-size:12.5px}
</style></head><body><div class="wrap">
<div class="nav"><a href="terms.html">Terms</a><a href="privacy.html">Privacy</a><a href="refunds.html">Billing &amp; Refunds</a><a href="feature_board.html">Plans</a></div>
<h1>%s</h1><div class="eff">%s &middot; Effective %s</div>
%s
<footer>&copy; %s %s (%s). Questions: <a href="mailto:%s">%s</a>%s<br>
This document is provided for transparency about how the service works; it is not legal advice to you.</footer>
</div></body></html>""" % (esc(title), esc(c["entity"]), esc(title), esc(c["entity"]), esc(c["effective"]),
        body, datetime.now(HST).year, esc(c["entity"]), esc(c["dba"]), esc(c["contact_email"]),
        esc(c["contact_email"]), (" &middot; " + esc(c["address"]) if c["address"] else ""))

def terms_body(c):
    return """
<p>These Terms of Service ("Terms") govern your access to and use of the %(entity)s civic-transparency
platform, including the public dashboards, the AI tools, the oversight calculators, and any paid
subscription (the "Service"), operated by %(entity)s ("we," "us"). By creating an account, verifying
your identity, subscribing, or otherwise using the Service, you agree to these Terms. If you do not
agree, do not use the Service.</p>

<h2>1. Eligibility &amp; accounts</h2>
<p>You must be at least 18 and able to form a binding contract. Free participation (submitting and
voting on public requests) requires a one-time identity verification performed by our processor
(Stripe Identity); this verification is free and is used to keep the public record one-person-one-voice.
You are responsible for activity under your account and for keeping your credentials secure.</p>

<h2>2. The Service; civic data; not legal advice</h2>
<p>The Service organizes <b>public records</b> (campaign finance, contracts, votes, permits, and
similar government data) and provides tools to analyze them. <b>Every finding is presented as a
question for the lawful channel, not as an accusation or a finding of wrongdoing.</b> The Service —
including any AI output, calculator result, or draft document — is <b>informational only and is not
legal, financial, or professional advice</b>, is not a substitute for an attorney, and creates no
attorney–client relationship. Drafts (e.g., proposed legislation or records requests) are starting
points you must independently verify before use.</p>

<h2>3. Subscriptions, billing &amp; automatic renewal</h2>
<p>Paid tiers are sold as <b>recurring subscriptions</b> billed in advance on a monthly or annual
cycle through our payment processor (Stripe). <b>Your subscription automatically renews</b> for
successive periods at the then-current price until you cancel. We disclose the price, billing
frequency, and renewal terms before you pay. <b>You may cancel at any time</b> through your account
or by emailing <a href="mailto:%(contact_email)s">%(contact_email)s</a>; cancellation stops the next
renewal and takes effect at the end of the current paid period. Billing, cancellation, and refund
details are in our <a href="refunds.html">Billing &amp; Refund Policy</a>, which is part of these Terms.
We may change prices on at least 30 days' notice; changes apply to the next renewal.</p>

<h2>4. Acceptable use</h2>
<p>You agree not to: misuse public-records data to harass, defame, or unlawfully target any person;
present the Service's outputs as established findings of guilt; resell or scrape the Service except
as permitted; interfere with the Service's security or operation; or use the Service in violation of
law. Private analysis available to paid accounts is for your own lawful oversight use and must remain
framed as questions for the appropriate official channel.</p>

<h2>5. Intellectual property</h2>
<p>The Service, its software, and its original content are owned by %(entity)s. Underlying government
records are public. We grant you a limited, non-exclusive, non-transferable license to use the Service
for its intended civic purpose. Content you submit (e.g., feature requests) you license to us to
operate and improve the Service.</p>

<h2>6. Disclaimers; no warranty</h2>
<p>The Service is provided <b>"as is" and "as available," without warranties of any kind</b>, express
or implied, including merchantability, fitness for a particular purpose, accuracy, or non-infringement.
We do not warrant that data is complete, current, or error-free; public sources change and may contain
errors. You are responsible for verifying any figure against its cited source before relying on it.</p>

<h2>7. Limitation of liability</h2>
<p>To the maximum extent permitted by law, %(entity)s will not be liable for any indirect, incidental,
special, consequential, or punitive damages, or any loss of data, reputation, or profits. Our total
liability for any claim relating to the Service will not exceed the greater of the amounts you paid us
in the 12 months before the claim or US$100.</p>

<h2>8. Indemnification</h2>
<p>You agree to indemnify and hold harmless %(entity)s from claims arising out of your misuse of the
Service or your violation of these Terms or of any law or third-party right.</p>

<h2>9. Governing law &amp; dispute resolution</h2>
<p>These Terms are governed by the laws of %(jurisdiction)s, without regard to conflict-of-laws rules.
Except where prohibited, you and %(entity)s agree to resolve disputes through binding individual
arbitration and to waive class actions; you may opt out of arbitration within 30 days of first
accepting these Terms by emailing us. Where arbitration does not apply, the exclusive venue is
%(venue)s. Nothing here limits any non-waivable consumer right you have under applicable law.</p>

<h2>10. Changes; termination; contact</h2>
<p>We may update these Terms; material changes will be posted with a new effective date and, for
subscribers, reasonable notice. We may suspend or terminate access for violation of these Terms.
Questions: <a href="mailto:%(contact_email)s">%(contact_email)s</a>.</p>
""" % c

def privacy_body(c):
    return """
<p>This Privacy Policy explains what %(entity)s ("we") collects, how we use it, and your choices. We
build for data minimization: the Service runs on <b>public records</b>, and we keep as little personal
information about <em>you</em> as possible.</p>

<h2>1. Information we collect</h2>
<ul>
<li><b>Account &amp; identity verification.</b> To keep the public record one-person-one-voice and to
meet payment requirements, identity verification is performed by <b>Stripe Identity</b>. Stripe
collects and processes your government ID and a selfie/liveness check and validates your name, date of
birth, and address. <b>Stripe stores the raw identity documents and images; we do not.</b> We receive
only a verification result and a token.</li>
<li><b>Payment information.</b> Subscriptions are processed by <b>Stripe</b>. <b>Stripe handles your
card data; we never receive or store full card numbers.</b> We keep a minimal billing record (tier,
status, dates) with no card or raw ID data.</li>
<li><b>Usage data.</b> Basic, privacy-respecting logs needed to operate and secure the Service. We do
not sell personal information.</li>
<li><b>Content you submit.</b> Public feature requests/votes you choose to make; private analyses you
run stay in your account and are not published.</li>
</ul>

<h2>2. How we use information</h2>
<p>To provide and secure the Service; to verify eligibility; to process subscriptions; to keep the
public request record honest (one verified person, one voice); to comply with law; and to improve the
Service. We do <b>not</b> sell your personal information and do <b>not</b> use your private analyses
to build a public profile of you.</p>

<h2>3. How we share</h2>
<p>With service providers who process data on our behalf under contract — principally <b>Stripe</b>
(identity + payments) and our hosting/infrastructure. We may disclose information if required by law.
We do not share your private account activity publicly. Public records about elected officials and
public spending are not "your" personal data and remain public.</p>

<h2>4. Your rights &amp; choices</h2>
<p>Depending on where you live (including California under the CCPA/CPRA and the EU/UK under the GDPR),
you may have the right to <b>access, correct, delete, or port</b> your personal information, to
<b>opt out of sale/sharing</b> (we do not sell), and to <b>not be discriminated against</b> for
exercising these rights. You can export or delete your account data at any time, or email
<a href="mailto:%(contact_email)s">%(contact_email)s</a>. For identity-document data, contact Stripe
as the processor of record; we will assist.</p>

<h2>5. Cookies</h2>
<p>We use only the cookies necessary to run the Service and keep you signed in. We do not use
third-party advertising or cross-site tracking cookies.</p>

<h2>6. Data retention &amp; security</h2>
<p>We retain the minimal billing/account records we keep for as long as your account is active and as
required by law, then delete or de-identify them. We use reasonable technical and organizational
safeguards (encryption in transit and at rest, least-privilege access). No method is perfectly secure,
but we design for a small blast radius and you own your data.</p>

<h2>7. Children</h2>
<p>The Service is not directed to children under 18 and we do not knowingly collect their data.</p>

<h2>8. International &amp; changes</h2>
<p>We operate from the United States; if you use the Service from elsewhere, you consent to processing
in the U.S. We may update this Policy; material changes will be posted with a new effective date.</p>

<h2>9. Contact</h2>
<p>%(entity)s — <a href="mailto:%(contact_email)s">%(contact_email)s</a>.</p>
""" % c

def refunds_body(c):
    return """
<p>This Billing, Auto-Renewal, Cancellation &amp; Refund Policy is part of our
<a href="terms.html">Terms of Service</a> and explains exactly how charges work, so there are no
surprises.</p>

<div class="box"><b>Plain-language summary.</b> Identity verification is <b>free</b>. Paid plans are
<b>monthly or annual subscriptions billed in advance</b> that <b>automatically renew until you cancel</b>.
You can <b>cancel anytime</b> — in your account or by emailing
<a href="mailto:%(contact_email)s">%(contact_email)s</a> — and you will not be billed again. See the
refund terms below.</div>

<h2>1. Free identity verification</h2>
<p>Creating a verified free account costs nothing. The identity check (Stripe Identity) is free to you;
nothing is charged at sign-up.</p>

<h2>2. Subscription plans &amp; pricing</h2>
<p>Paid tiers are shown on the <a href="feature_board.html">Plans</a> page with their price and billing
frequency. The price and cycle (monthly or annual) shown at checkout are the price and cycle you pay.</p>

<h2>3. Automatic renewal (please read)</h2>
<p><b>Your subscription renews automatically</b> at the end of each billing period (monthly or annual)
at the then-current price, and your payment method is charged, <b>until you cancel</b>. We disclose
this before you subscribe and at checkout. We may notify you before an annual renewal where required by
law.</p>

<h2>4. How to cancel</h2>
<p>You may cancel at any time, with no fee, either through your account's billing settings (Stripe
customer portal) or by emailing <a href="mailto:%(contact_email)s">%(contact_email)s</a>. Cancellation
stops the next renewal. Your access continues through the end of the period you already paid for.</p>

<h2>5. Refunds</h2>
<p>Because access is delivered immediately and continuously, <b>payments for the current period are
generally non-refundable</b>, except: (a) where a refund is required by applicable law; (b) a duplicate
or erroneous charge; or (c) at our discretion for a documented service failure. If you believe you were
charged in error, email us within 30 days and we will make it right. Cancelling stops future charges
but does not by itself refund the current period.</p>

<h2>6. Failed payments &amp; price changes</h2>
<p>If a renewal payment fails, we may retry and may suspend paid access until payment succeeds. We will
give at least 30 days' notice of any price increase; it applies only to renewals after the notice, and
you may cancel before it takes effect.</p>

<h2>7. Nothing is charged until Stripe checkout</h2>
<p>No charge occurs until you complete payment on Stripe's secure hosted checkout. A checkout session
is not a charge; only completing it on Stripe charges your method.</p>

<h2>8. Contact</h2>
<p>Billing questions: <a href="mailto:%(contact_email)s">%(contact_email)s</a>.</p>
""" % c

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    c = cfg()
    out = {
        "terms.html":   page("Terms of Service", terms_body(c), c),
        "privacy.html": page("Privacy Policy", privacy_body(c), c),
        "refunds.html": page("Billing, Auto-Renewal, Cancellation & Refund Policy", refunds_body(c), c),
    }
    for fn, htmlc in out.items():
        open(os.path.join(MAUIOS, fn), "w", encoding="utf-8", newline="\n").write(htmlc)
        print("  + %s" % fn)
    print("legal_pages: wrote %d standard legal pages -> reports/mauios/ (entity=%s, contact=%s). "
          "Finalize config/legal.json (entity/address) + have counsel do a final pass." % (len(out), c["entity"], c["contact_email"]))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
