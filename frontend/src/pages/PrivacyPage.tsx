export default function PrivacyPage() {
  return (
    <article className="legal-document">
      <h1>Privacy Policy</h1>
      <p>MyPlaylist is a music-focused social application where people can create an account, build a ranked Top 10 of songs, and interact with other users.</p>

      <h2>Information we use</h2>
      <p>When you register, we process your email address, display name, and password. Passwords are stored as secure hashes, not as readable text. We also store account and session information needed to sign you in.</p>
      <p>We store the profile information and content you choose to provide, such as your biography, ranked songs, friendships, and interactions with other users.</p>

      <h2>Why we use it</h2>
      <p>We use this information to authenticate accounts, show profiles and Top 10 lists, support social features, and keep the application functioning. We do not need your real name to create a MyPlaylist account.</p>

      <h2>Who can see your information</h2>
      <p>Your display name and the profile information made visible through the application may be seen by other users. Your Top 10 visibility can be controlled in your profile settings. Do not include sensitive personal information in public profile content.</p>
      <p>Your password is not displayed to other users. The application uses a session cookie to keep you signed in.</p>

      <h2>Managing your information</h2>
      <p>You can update your display name, biography, and Top 10 visibility in Settings, and edit your song list from your profile. In Settings, you can download a JSON copy of your account and profile, uploaded avatar, Top 10, friendships, blocks, comments, reactions, received notifications, and messages you sent or received. The export excludes password hashes, session tokens, and other users’ private information. We attempt to email a confirmation without the export, but email failure does not stop the download.</p>

      <h2>Deleting your account</h2>
      <p>In Settings, you can request an account deletion email. The token in that email expires after 15 minutes. While signed in, you must enter the token and explicitly type DELETE to confirm. We limit repeat requests to one every five minutes. If the confirmation email cannot be delivered, deletion cannot proceed. You can leave the flow without deleting your account.</p>
      <p>After confirmation, we permanently delete your account, profile, uploaded avatar, Top 10, friendships, blocks, authored comments and reactions, received notifications, messages you sent or received, and sessions. Comments and reactions on your Top 10 also disappear with that list. Shared songs, unrelated conversations, and other users’ accounts remain. Notifications retained by other users are changed to remove your actor identifier and custom message. A completion email is attempted after deletion; delivery failure does not restore the account.</p>
      <p>This flow applies to active accounts. Accounts disabled under earlier versions are a separate remediation concern and are not automatically erased by this feature.</p>

      <h2>Questions</h2>
      <p>For questions about information held in this project or requests not available in the interface, contact the project team through the repository linked below.</p>

      <h2>About this project</h2>
      <p>MyPlaylist is a student project developed as part of the 42 curriculum. This policy describes the current application behavior and does not claim complete legal GDPR compliance.</p>
      <p><a href="https://github.com/jomunoz42/ft_transcendence">Project repository</a></p>
    </article>
  )
}
