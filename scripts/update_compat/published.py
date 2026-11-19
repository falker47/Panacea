"""SHA-256 pins of the original release assets. Check before install or PYZ access."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pins:
    exe: str
    setup: str


PUBLISHED = {
    "v2.0.0": Pins("3e483228dbef5fd1298777382a848aa5eb92a883c64c93873cfe03d64c79c0ed",
                   "3ce5bd6ad47c45b668eefdafbcb8687d5db4742bb29e88142259c99540729b26"),
    "v2.0.1": Pins("abb1b95410c29147686dc4be4acfe3dd5586f74e64cf08de0f1d9bdf5d1f7119",
                   "8a9e89a49edcbd5f37a09633642bcf0fcde37b1371d76d99c1883f166e2747a9"),
    "v2.0.2": Pins("e390d2f26f84e108c0e076d834f61927554a77175fe19c22108667f04ec1161f",
                   "43568f813848aa75e2cb92c0bc207a8f2e08788e5614910ad19847c008bc81f1"),
    "v2.1.0": Pins("684121592593afd16042fceab7b6027bf81718aab276fc024ae6d6bf5baf056c",
                   "e60bc29b12b3e4016f891e1e231689b8d82d2c1f6c788a291eb869e1833b9509"),
    "v2.1.1": Pins("c74c860f3c6e132301b4020cf0a9abc296f183c2af2be508444713e9583cbd98",
                   "56b9c5d35a9be4469a3bb54a3394fa2969765c632ffc2b0bb4e61077e2bc36ab"),
}
