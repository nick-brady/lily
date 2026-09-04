import LegalLayout, { LegalSection } from '../components/LegalLayout';

const SUPPORT_EMAIL = 'help@arrivalstory.com';

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" updated="September 4, 2026">
      <LegalSection heading="Agreement">
        <p>
          These terms are an agreement between you and Arrival Story ("we", "us") covering
          your use of arrivalstory.com. By creating an account, accepting an invitation, or
          using the service, you agree to them. If you don't agree, please don't use the
          service.
        </p>
      </LegalSection>

      <LegalSection heading="The service">
        <p>
          Arrival Story lets parents create a private page for their baby's arrival —
          contraction timing, updates, photos, and milestones — and share it with invited
          family members in real time. We also offer optional paid extras: long-term page
          storage and physical keepsakes made from your page's content.
        </p>
      </LegalSection>

      <LegalSection heading="Accounts">
        <p>
          You must be 18 or older to create an account. You sign in with a one-time code
          sent to your email address or mobile number; keep access to that address or
          number secure, since anyone who controls it can access your account. You're
          responsible for activity under your account.
        </p>
      </LegalSection>

      <LegalSection heading="Your content">
        <p>
          You own everything you post. You grant us only the license we need to host,
          store, display, and (for keepsakes you order) print your content to provide the
          service. We never use your family's content for advertising.
        </p>
        <p>
          You're responsible for what you share. Only post content you have the right to
          share, and only share a page with people you trust — visibility controls decide
          who sees what, but the people you invite can see what you make visible to them.
        </p>
      </LegalSection>

      <LegalSection heading="Invitations">
        <p>
          When you enter someone's phone number or email address to invite them, you
          confirm you personally know them and reasonably believe they'd welcome the
          invitation. Each invitation identifies you by name, is sent once, and includes
          opt-out instructions. Don't use invitations to send bulk, commercial, or
          unwelcome messages.
        </p>
      </LegalSection>

      <LegalSection heading="Text messaging terms">
        <p>By providing your mobile number, you consent to receive text messages from Arrival Story, limited to:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>one-time sign-in codes you request;</li>
          <li>invitations a family member personally sends you;</li>
          <li>a single "first day" memory update after a birth on a page you joined;</li>
          <li>a yearly memory message about your own page.</li>
        </ul>
        <p>
          Message frequency varies and is low. Message and data rates may apply. Reply
          STOP at any time to stop receiving texts, and HELP for help or contact{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary-600 dark:text-primary-400 hover:underline">{SUPPORT_EMAIL}</a>.
          Carriers are not liable for delayed or undelivered messages. Note that opting
          out of SMS also stops sign-in codes by text — you can still sign in by email.
        </p>
      </LegalSection>

      <LegalSection heading="Purchases">
        <p>
          Payments are processed by Stripe. Prices are shown before you pay; postage is
          quoted for the address at checkout and charged on top. Storage plans keep a page
          live for the period purchased; when a plan lapses the page moves to archived
          storage and can be reactivated.
        </p>
        <p>
          <strong>Keepsakes are made to order</strong>, each one from a single family's
          page, so they can't be resold and generally can't be returned. What that means
          in practice:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>Cancelling.</strong> You can cancel for a full refund any time before we
            send your order to print — usually within a day of ordering. Your receipt page
            has a cancel button until then; after that, email{' '}
            <a href="mailto:help@arrivalstory.com" className="underline underline-offset-2">help@arrivalstory.com</a>{' '}
            with your order reference.
          </li>
          <li>
            <strong>Once it's in production</strong>, we can't refund a change of mind: the
            item already exists, and it's yours.
          </li>
          <li>
            <strong>Damaged, defective or wrong.</strong> If it arrives broken, misprinted, or
            not what you ordered, we replace it or refund you, no argument. Email us a photo
            within 30 days of delivery.
          </li>
          <li>
            <strong>Addresses.</strong> Orders ship to the address given at checkout, or the
            family's saved address. Please check it; we can't recover a parcel sent to a wrong
            address, though we'll help however we can.
          </li>
        </ul>
        <p>
          Refunds go back to the card that paid and usually appear within a few days.
        </p>
      </LegalSection>

      <LegalSection heading="Acceptable use">
        <p>
          Don't misuse the service: no unlawful content, no harassment, no attempting to
          access other families' pages, no scraping, and no interfering with the service's
          operation. We may remove content or suspend accounts that violate these terms.
        </p>
      </LegalSection>

      <LegalSection heading="Ending service">
        <p>
          You can stop using Arrival Story at any time and request deletion of your
          account. We may suspend or terminate access for violations of these terms. If we
          ever discontinue the service, we'll give you a reasonable opportunity to export
          your content first.
        </p>
      </LegalSection>

      <LegalSection heading="Disclaimers and liability">
        <p>
          Arrival Story is provided "as is" without warranties of any kind. It is a
          memory-keeping service, not a medical device — contraction timing and related
          features are for keepsake purposes and are not medical advice; always follow
          your care provider's guidance. To the fullest extent permitted by law, our total
          liability for any claim relating to the service is limited to the amount you
          paid us in the twelve months before the claim.
        </p>
      </LegalSection>

      <LegalSection heading="Changes and contact">
        <p>
          We may update these terms; if we make material changes we'll update the date
          above and note it on the site. Continuing to use the service after changes take
          effect means you accept them. Questions? Email{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary-600 dark:text-primary-400 hover:underline">{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
