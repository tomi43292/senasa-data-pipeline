from senasa_pipeline.domain.entities.senasa_record import SenasaRecord


class ValidateSenasaRecordUseCase:
    def __init__(self, validator):
        self.validator = validator

    def execute(self, record: SenasaRecord) -> bool:
        return self.validator.validate(record)
