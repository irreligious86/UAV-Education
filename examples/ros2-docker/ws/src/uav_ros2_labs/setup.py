from setuptools import setup

package_name = "uav_ros2_labs"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/px4_square.launch.py", "launch/ap_square.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "telemetry_logger = uav_ros2_labs.telemetry_logger:main",
            "px4_offboard_square = uav_ros2_labs.px4_offboard_square:main",
            "ap_dds_square = uav_ros2_labs.ap_dds_square:main",
        ],
    },
)
