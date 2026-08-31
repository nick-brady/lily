import LegalLayout, { LegalSection } from '../components/LegalLayout';

const SUPPORT_EMAIL = 'nicholas.aaron.brady@gmail.com';

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" updated="August 30, 2026">
      <LegalSection heading="Who we are">
        <p>
          Arrival Story ("we", "us") operates arrivalstory.com, a private family
          birth-announcement service. Parents create a page for their baby's arrival, and
          invited family members follow along. This policy explains what information we
          collect, how we use it, and the choices you have.
        </p>
      </LegalSection>

      <LegalSection heading="Information we collect">
        <p>
          <strong>Account information.</strong> Your name and the email address or mobile
          phone number you sign in with.
        </p>
        <p>
          <strong>Content you share.</strong> Photos, audio, posts, comments, reactions,
          contraction timings, and other content you or your family add to a birth page.
          This content is visible only to the people the page's parents invite, at the
          visibility levels they choose.
        </p>
        <p>
          <strong>Purchase information.</strong> If you buy storage or a keepsake gift,
          payments are processed by Stripe — we never see or store your card number. For
          physical keepsakes we collect a shipping address to fulfill the order.
        </p>
        <p>
          <strong>Usage data.</strong> Our web server keeps short-lived technical logs
          (including IP address and browser type) for security and reliability. Separately,
          we count page views ourselves — see{' '}
          <a href="#analytics" className="text-primary-600 dark:text-primary-400 hover:underline">
            Analytics and cookies
          </a>{' '}
          below.
        </p>
      </LegalSection>

      <LegalSection heading="How we use your information">
        <p>We use your information only to run Arrival Story:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>signing you in with one-time codes and magic links;</li>
          <li>delivering invitations that a parent or co-parent personally sends;</li>
          <li>
            sending the small number of service messages described in our{' '}
            <a href="/terms" className="text-primary-600 dark:text-primary-400 hover:underline">Terms</a>{' '}
            (such as a first-day memory update and a yearly memory message);
          </li>
          <li>fulfilling keepsake orders and storage purchases;</li>
          <li>keeping the service secure and working.</li>
        </ul>
        <p>We do not run ads, and we do not sell your personal information. Ever.</p>
      </LegalSection>

      <LegalSection heading="Analytics and cookies" id="analytics">
        <p>
          We count page views ourselves, on our own servers. We do not use Google
          Analytics or any other third-party analytics service, and there are no
          advertising or tracking networks anywhere on this site.
        </p>
        <p>
          For each page you open we record the page address, the site that linked you here
          (on your first page only), any campaign tag in the link you arrived by, your
          browser&rsquo;s user-agent string, and the time. <strong>We do not store your IP
          address alongside it.</strong> If you are signed in, the visit is linked to your
          account so we can tell how the service is actually used; if you are not, it is
          simply an anonymous count. Deleting your account unlinks your past visits, leaving
          the counts without you in them.
        </p>
        <p>
          <strong>Cookies and local storage.</strong> We set one cookie: the one that
          keeps you signed in. It is strictly necessary for the service to work, so there is
          no cookie banner to click through. Your browser also keeps two small items for us
          on your own device &mdash; whether you prefer dark mode, and which link first
          brought you here so that credit is not reassigned if you come back another way.
          Neither is an advertising identifier, and none of this is shared with anyone.
        </p>
        <p>
          The fonts and other files this site loads are served from our own servers, so
          opening a page does not tell any third party that you visited.
        </p>
      </LegalSection>

      <LegalSection heading="Text messaging (SMS) privacy">
        <p>
          No mobile information will be shared with third parties or affiliates for
          marketing or promotional purposes. Text messaging originator opt-in data and
          consent will not be shared with any third parties, excluding the messaging
          providers we use to deliver messages to you.
        </p>
        <p>
          You can stop all text messages at any time by replying STOP, and get help by
          replying HELP. Message and data rates may apply; message frequency varies.
        </p>
      </LegalSection>

      <LegalSection heading="When we share information">
        <p>
          We share information only with the service providers that make Arrival Story
          work, and only what each needs to do its job: Twilio (SMS delivery), Resend
          (email delivery), Stripe (payments), Amazon Web Services (hosting and media
          storage), and our print-fulfillment partner (name and shipping address for
          keepsake orders). We may also disclose information if required by law.
        </p>
      </LegalSection>

      <LegalSection heading="Your choices">
        <ul className="list-disc pl-5 space-y-1">
          <li>Reply STOP to any text message to opt out of SMS.</li>
          <li>You can export your family's page content as a download.</li>
          <li>
            You can delete your account at any time from your account page — this
            permanently erases your sign-in details and any birth pages only you
            manage. Need a hand, or want something more specific removed? Email{' '}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary-600 dark:text-primary-400 hover:underline">{SUPPORT_EMAIL}</a>{' '}
            and we'll take care of it.
          </li>
        </ul>
      </LegalSection>

      <LegalSection heading="Data retention">
        <p>
          Birth pages are kept for as long as the page's storage plan is active. Lapsed
          pages are moved to archived storage rather than deleted, so families can
          reactivate them later. Sign-in codes expire within minutes and are not reused.
        </p>
      </LegalSection>

      <LegalSection heading="Children">
        <p>
          Arrival Story pages are about babies, but accounts are for adults. You must be
          18 or older to create an account, and we do not knowingly collect personal
          information from children under 13. Photos and details about a child are added
          by that child's own family, who control who can see them.
        </p>
      </LegalSection>

      <LegalSection heading="Security">
        <p>
          All traffic is encrypted in transit (HTTPS), media is stored in access-controlled
          cloud storage, and sign-in uses short-lived one-time codes rather than passwords.
          No system is perfectly secure, but we design for your family's privacy first.
        </p>
      </LegalSection>

      <LegalSection heading="Changes and contact">
        <p>
          If we change this policy, we'll update the date at the top and, for material
          changes, note it on the site. Questions? Email{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary-600 dark:text-primary-400 hover:underline">{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
