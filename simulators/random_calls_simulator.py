import random
from   models.models import DeliveryCall


class RandomCallsSimulator:
    def __init__(self, hospitals, seed=None):
        self.hospitals = hospitals
        self.next_id = 1
        if seed is not None:
            random.seed(seed)

    def maybe_generate_call(self, current_minute: int, probability: float = 0.15):
        if random.random() > probability:
            return None

        origin, destination = random.sample(self.hospitals, 2)
        payload = round(random.uniform(0.5, 4.5), 2)
        priority = random.choices([1, 2, 3], weights=[0.2, 0.5, 0.3])[0]

        call = DeliveryCall(
            call_id=self.next_id,
            timestamp_min=current_minute,
            origin_hospital=origin,
            destination_hospital=destination,
            payload_kg=payload,
            priority=priority,
        )
        self.next_id += 1
        return call