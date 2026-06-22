import { redirect } from "next/navigation";

// The official landing page now lives at the root route (`/`).
// Keep `/landing` as a permanent redirect so old links and bookmarks resolve.
export default function LandingRedirect() {
  redirect("/");
}
