class LongFieldsException(Exception):
    def __init__(self, long_fields, max_length):
        self.long_fields = long_fields
        self.max_length = max_length

    @property
    def message(self):
        message = ''
        for table, headers in self.long_fields.items():
            message += (
                'Table "{}" has field names longer than the maximum allowed for this database ({}):\n'.format(
                table, self.max_length
            ))
            for header in headers:
                message += '    {}\n'.format(header)

        message += '\nPlease adjust field names to be within the maximum length limit of {}'.format(self.max_length)
        return message
