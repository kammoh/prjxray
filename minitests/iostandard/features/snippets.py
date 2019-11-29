import os
import argparse

from collections import namedtuple

IOSettings = namedtuple("IOSettings", "iostandard, drive, slew")

# =============================================================================


def load_feature_data(fname):
    """
    Load feature vs. IO settings correlation data from a CSV file.
    """
    feature_data = {}

    # Open the file
    with open(fname, "r") as fp:

        # Header
        line = fp.readline()
        features = line.strip().split(",")[1:]

        # Data
        for line in fp:
            fields = line.strip().split(",")

            # IOSettings
            parts = fields[0].split(".")
            ios = IOSettings(
                parts[0],
                int(parts[1][1:]) if parts[1][1:] != "_FIXED" else None,
                parts[2])

            # Feature activity
            feature_data[ios] = {
                f: fields[1 + i]
                for i, f in enumerate(features)
            }

    return feature_data


def filter_feature_data(feature_data):
    """
    Filters fasm features and leaves only those related to IO settings.
    """

    for data in feature_data.values():
        for feature in dict(data):

            if "DISABLE" in feature:
                del data[feature]
            if "PULLTYPE" in feature:
                del data[feature]
            if "IN_TERM" in feature:
                del data[feature]
            if "LOW_PWR" in feature:
                del data[feature]

    return feature_data


def get_relevant_parameters(feature_data, iob_type):
    """
    Gets features relevant to a specific IOB type and assign them verilog
    parameter names.
    """

    # Get all features and make parameter names
    all_features = set(
        [f for data in feature_data.values() for f in data.keys()])
    parameters = []

    # Check if a feature is relevant to particular IOB type
    for feature in all_features:
        for iosettings in feature_data:
            if iob_type in feature_data[iosettings][feature]:
                parameters.append((
                    feature,
                    feature.replace(".", "_"),
                ))
                break

    return parameters


# =============================================================================


def generate_parameter_defs(parameters):
    """
    Generates verilog parameter definitions for the IOB cell model.
    """
    verilog = []

    for feature, parameter in sorted(parameters):
        verilog.append("parameter [0:0] {} = 1'b0".format(parameter))

    return ";\n".join(verilog)


def generate_parameter_map(parameters):
    """
    Generates mapping of parameters for fasm features for architecture
    definition.
    """
    xml = []

    xml.append("<meta name=\"fasm_params\">")
    for feature, parameter in sorted(parameters):
        xml.append("  {} = {}".format(feature, parameter))
    xml.append("</meta>")

    return "\n".join(xml)


def generate_parameter_assignments(parameters, feature_data, iob_type):
    """
    Generates parameter assignmets to be used inside the techmap. For
    each IOB cell parameter a set of conditions is generated based on
    feature activity observation.
    """
    verilog = []

    for feature, parameter in sorted(parameters):
        condition = []
        for iosettings in feature_data:

            # Feature is set
            if iob_type in feature_data[iosettings][feature]:
                cond = "IOSTANDARD == \"{}\"".format(
                    iosettings.iostandard.upper())

                if iob_type in ["O", "T"]:
                    if iosettings.drive is not None and "DRIVE" in feature:
                        cond += " && DRIVE == {}".format(iosettings.drive)
                    if "SLEW" in feature:
                        cond += " && SLEW == \"{}\"".format(iosettings.slew)

                condition.append(cond)

        condition = sorted(list(set(condition)))

        condition_str = " || \n".join(["  ({})".format(c) for c in condition])
        verilog.append(".{}(\n{}\n)".format(parameter, condition_str))

    return ",\n".join(verilog)


# =============================================================================


def run():
    """
    Main.
    """

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=str, help="Input CSV file")

    args = parser.parse_args()

    # Load iosettings vs. feature map
    feature_data = load_feature_data(args.features)
    # Reject non-iostandard related features
    feature_data = filter_feature_data(feature_data)

    # Make parameters
    parameters = {}
    for iob_type in ["I", "O", "T"]:
        parameters[iob_type] = get_relevant_parameters(feature_data, iob_type)

    # Parameter definition
    with open("cells_sim.v", "w") as fp:
        for iob_type, params in parameters.items():
            fp.write("// {} {}\n\n".format(iob_type, "=" * 70))
            verilog = generate_parameter_defs(params)
            fp.write(verilog + "\n\n")

    # Parameter assignments
    with open("cells_map.v", "w") as fp:
        for iob_type, params in parameters.items():
            fp.write("// {} {}\n\n".format(iob_type, "=" * 70))
            verilog = generate_parameter_assignments(
                params, feature_data, iob_type)
            fp.write(verilog + "\n\n")

    # Parameter assignments
    with open("arch.xml", "w") as fp:
        for iob_type, params in parameters.items():
            fp.write("<!-- {} -->\n\n".format(iob_type))
            xml = generate_parameter_map(params)
            fp.write(xml + "\n\n")


if __name__ == "__main__":
    run()
