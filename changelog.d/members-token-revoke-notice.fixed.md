- The members page no longer claims that a demoted member's API tokens keep
  their old role until revoked. Since the API revokes all of a member's tokens
  in the workspace on every role change, the page now says so after each role
  change — upgrades included — and that new tokens get the new role. ADR-0023
  carries a dated addendum pointing to the implementation.
