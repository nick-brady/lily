import LegalLayout, { LegalSection } from '../components/LegalLayout';

const SUPPORT_EMAIL = 'nicholas.aaron.brady@gmail.com';

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" updated="July 5, 2026">
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
          <strong>Usage data.</strong> Basic technical logs (such as IP address and browser
          type) generated when you use the service, used for security and reliability.
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
            To delete your account or content, email{' '}
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
