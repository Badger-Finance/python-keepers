class EmissionsSchedule:
    def __init__(self, schedule_json: dict):
        self.schedule_json = dict(schedule_json)
        self.dates = list(schedule_json.keys())
        self.start_times = self.get_start_times()
        self.end_times = self.get_start_times()
        self.setts = self.get_setts()
        self.formatted_schedule = self._create_formatted_schedule()

    def get_start_times(self) -> list:
        start_times = []
        for date in self.dates:
            start_times.append(self.schedule_json[date]["timerange"]["starttime"])
        return start_times

    def get_end_times(self) -> list:
        end_times = []
        for date in self.dates:
            end_times.append(self.schedule_json[date]["timerange"]["endtime"])
        return end_times

    def format_setts(self, setts_list: list) -> dict:
        setts_dict = {}
        for sett in setts_list:
            setts_dict[sett.pop("address")] = sett
        return setts_dict

    def get_setts(self) -> list:
        setts = []
        for date in self.dates:
            setts.append(self.format_setts(self.schedule_json[date]["setts"]))
        return setts

    def _create_formatted_schedule(self):
        schedule = {}
        index = 0
        for start_time in self.start_times:
            schedule[start_time] = self.setts[index]
            index += 1

        return schedule

    def get_schedule(self):
        return self.formatted_schedule
