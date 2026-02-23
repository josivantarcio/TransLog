import httpx

from app.core.config import settings


class PaymentService:
    """Integração com o gateway de pagamento Asaas."""

    def __init__(self) -> None:
        self._base_url = settings.ASAAS_API_URL
        self._headers = {
            "access_token": settings.ASAAS_API_KEY,
            "Content-Type": "application/json",
        }

    async def create_customer(self, name: str, email: str, document: str | None = None) -> dict:
        """Cria um cliente no Asaas para o tenant."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/customers",
                headers=self._headers,
                json={"name": name, "email": email, "cpfCnpj": document},
            )
            response.raise_for_status()
            return response.json()

    async def create_subscription(
        self,
        customer_id: str,
        value: float,
        billing_type: str = "CREDIT_CARD",
        cycle: str = "MONTHLY",
        description: str = "Assinatura transLog",
    ) -> dict:
        """Cria uma assinatura recorrente no Asaas."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/subscriptions",
                headers=self._headers,
                json={
                    "customer": customer_id,
                    "billingType": billing_type,
                    "value": value,
                    "cycle": cycle,
                    "description": description,
                },
            )
            response.raise_for_status()
            return response.json()

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verifica a assinatura HMAC do webhook Asaas."""
        import hashlib
        import hmac

        expected = hmac.new(
            settings.ASAAS_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
