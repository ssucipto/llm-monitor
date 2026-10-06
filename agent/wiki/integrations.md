# Service Integrations — XML-tagged sections, load one section at a time
# TODO: Replace with your actual external service config. Delete unused sections.

<database>
  type: YOUR_DB_TYPE  # e.g. PostgreSQL, MongoDB, Firebase
  host: YOUR_HOST
  schemas: []        # list main schemas/collections
</database>

<auth>
  provider: YOUR_AUTH_PROVIDER  # e.g. Auth0, Firebase Auth, custom JWT
  flows: []                      # e.g. email-password, oauth-google
</auth>

<external_apis>
  # List any third-party APIs your project calls
  # - name: Stripe
  #   base_url: https://api.stripe.com
  #   env_var: STRIPE_SECRET_KEY
</external_apis>
