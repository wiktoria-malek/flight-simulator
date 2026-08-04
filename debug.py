def insert_screen(self, screen_name):
    info = self._get_screen_movement_info(screen_name)

    if info["has_custom_screen_mover"]:
        setpoints = info["screen_mover_fields"].get("setpoints", {})

        target_label = None
        for candidate in ("screen", "in", "screen in", "insert", "inserted"):
            for label in setpoints:
                label_norm = str(label).strip().lower().replace("_", " ").replace("-", " ")
                label_norm = " ".join(label_norm.split())
                if label_norm == candidate:
                    target_label = label
                    break
            if target_label is not None:
                break

        if target_label is None:
            raise RuntimeError(f"No insert position configured for {screen_name}")

        target_value = int(setpoints[target_label])

        current_data = self.client.get(
            f"{info['screen_mover_device']}/Acquisition",
            context=self.context_empty,
        ).data
        current_value = int(current_data["position"])

        if current_value == target_value:
            self.log(f"Screen {screen_name} already inserted")
            return

        self.log(f"Inserting {screen_name} to '{target_label}'...")

        if info["screen_mover_type"] == "BStepMotorVME":
            self.client.set(
                f"{info['screen_mover_device']}/Move",
                data={"mode": 2, "value": target_value, "units": 2},
            )
        elif info["screen_mover_type"] == "NewFocusPicomotor":
            self.client.set(
                f"{info['screen_mover_device']}/Setting",
                data={"position": target_value},
            )
        else:
            raise RuntimeError(
                f"Unsupported screen mover type {info['screen_mover_type']} for {screen_name}"
            )

        reached_target = self._wait_for_screen_target_position(screen_name, target_value)
        if not reached_target:
            raise RuntimeError(f"Screen {screen_name} was not inserted within time.")

        self.log(f"Inserted {screen_name}!")
        return

    if info["ctrl_type"] == "BTVCTRL":
        description = self.client.get(
            f"{info['btvdevice']}/Description",
            context=self.context_empty,
        ).data[info["description_field"]]

        position_names = [
            str(getattr(x, "value", x)).strip()
            for x in list(description)
            if str(getattr(x, "value", x)).strip()
        ]

        target_index = None
        for candidate in ("screen in", "in", "screen", "insert", "inserted"):
            for i, name in enumerate(position_names):
                name_norm = str(name).strip().lower().replace("_", " ").replace("-", " ")
                name_norm = " ".join(name_norm.split())
                if name_norm == candidate:
                    target_index = i
                    break
            if target_index is not None:
                break

        if target_index is None:
            target_index = 1 if len(position_names) > 1 else 0

        current_status = self.client.get(
            f"{info['btvdevice']}/{info['get_prop']}",
            context=self.context_empty,
        ).data[info["get_set_field"]]
        current_value = int(getattr(current_status, "value", current_status))

        if current_value == target_index:
            self.log(f"Screen {screen_name} already inserted")
            return

        self.log(f"Inserting {screen_name}...")

        self.client.set(
            f"{info['btvdevice']}/{info['set_prop']}",
            data={info["get_set_field"]: target_index},
        )

        reached_target = self._wait_for_screen_target_position(screen_name, target_index)
        if not reached_target:
            raise RuntimeError(f"Screen {screen_name} was not inserted within time.")

        self.log(f"Inserted {screen_name}!")
        return

    raise RuntimeError(f"Unsupported controlDeviceType for {screen_name}: {info['ctrl_type']}")


def extract_screen(self, screen_name):
    info = self._get_screen_movement_info(screen_name)

    if info["has_custom_screen_mover"]:
        setpoints = info["screen_mover_fields"].get("setpoints", {})

        target_label = None
        for candidate in ("out", "screen out", "extract", "extracted"):
            for label in setpoints:
                label_norm = str(label).strip().lower().replace("_", " ").replace("-", " ")
                label_norm = " ".join(label_norm.split())
                if label_norm == candidate:
                    target_label = label
                    break
            if target_label is not None:
                break

        if target_label is None:
            raise RuntimeError(f"No extract position configured for {screen_name}")

        target_value = int(setpoints[target_label])

        current_data = self.client.get(
            f"{info['screen_mover_device']}/Acquisition",
            context=self.context_empty,
        ).data
        current_value = int(current_data["position"])

        if current_value == target_value:
            self.log(f"Screen {screen_name} already extracted")
            return

        self.log(f"Extracting {screen_name} to '{target_label}'...")

        if info["screen_mover_type"] == "BStepMotorVME":
            self.client.set(
                f"{info['screen_mover_device']}/Move",
                data={"mode": 2, "value": target_value, "units": 2},
            )
        elif info["screen_mover_type"] == "NewFocusPicomotor":
            self.client.set(
                f"{info['screen_mover_device']}/Setting",
                data={"position": target_value},
            )
        else:
            raise RuntimeError(
                f"Unsupported screen mover type {info['screen_mover_type']} for {screen_name}"
            )

        reached_target = self._wait_for_screen_target_position(screen_name, target_value)
        if not reached_target:
            raise RuntimeError(f"Screen {screen_name} was not extracted within time.")

        self.log(f"Extracted {screen_name}!")
        return

    if info["ctrl_type"] == "BTVCTRL":
        description = self.client.get(
            f"{info['btvdevice']}/Description",
            context=self.context_empty,
        ).data[info["description_field"]]

        position_names = [
            str(getattr(x, "value", x)).strip()
            for x in list(description)
            if str(getattr(x, "value", x)).strip()
        ]

        target_index = None
        for candidate in ("screen out", "out", "extract", "extracted"):
            for i, name in enumerate(position_names):
                name_norm = str(name).strip().lower().replace("_", " ").replace("-", " ")
                name_norm = " ".join(name_norm.split())
                if name_norm == candidate:
                    target_index = i
                    break
            if target_index is not None:
                break

        if target_index is None:
            target_index = 0

        current_status = self.client.get(
            f"{info['btvdevice']}/{info['get_prop']}",
            context=self.context_empty,
        ).data[info["get_set_field"]]
        current_value = int(getattr(current_status, "value", current_status))

        if current_value == target_index:
            self.log(f"Screen {screen_name} already extracted")
            return

        self.log(f"Extracting {screen_name}...")

        self.client.set(
            f"{info['btvdevice']}/{info['set_prop']}",
            data={info["get_set_field"]: target_index},
        )

        reached_target = self._wait_for_screen_target_position(screen_name, target_index)
        if not reached_target:
            raise RuntimeError(f"Screen {screen_name} was not extracted within time.")

        self.log(f"Extracted {screen_name}!")
        return

    raise RuntimeError(f"Unsupported controlDeviceType for {screen_name}: {info['ctrl_type']}")


def _wait_for_screen_target_position(self, screen_name, target, timeout=10.0, poll_interval=0.05):
    info = self._get_screen_movement_info(screen_name)
    target = int(target)
    t0 = time.perf_counter()
    last_value = None

    while time.perf_counter() - t0 < timeout:
        if info["has_custom_screen_mover"]:
            current_data = self.client.get(
                f"{info['screen_mover_device']}/Acquisition",
                context=self.context_empty,
            ).data
            last_value = int(current_data["position"])

        elif info["ctrl_type"] == "BTVCTRL":
            current_status = self.client.get(
                f"{info['btvdevice']}/{info['get_prop']}",
                context=self.context_empty,
            ).data[info["get_set_field"]]
            last_value = int(getattr(current_status, "value", current_status))

        else:
            raise RuntimeError(
                f"Unsupported controlDeviceType for {screen_name}: {info['ctrl_type']}"
            )

        if last_value == target:
            return True

        time.sleep(poll_interval)

    self.log(
        f"Warning: {screen_name} did not reach target state = {target} "
        f"within {timeout:.2f}s. Last readback = {last_value}"
    )
    return False