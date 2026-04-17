import os
from pathlib import Path
from benchmark_paths import (
    benchmarks_root,
    classic_esop_benchmark_dir,
    epfl_benchmark_root,
    mcnc_benchmark_root,
)
from function import Function
from product import Product
from blif_parser import BLIFToESOP, BLIFBatchConverter

class RPLA:
    totalProducts = 0
    totalLiterals = 0
    totalOutputs = 0
    selectedMenu = 0
    selectedBenchmarkSubdir = None
    esopFileName = ""
    functions = []
    products = []
    patternsOfProduct = []
    time = 0

    def __init__(self):
        pass

    def resolve_input_file(self, fileName):
        file_path = Path(fileName)
        project_root = Path(__file__).resolve().parent.parent
        source_dirs = []

        if self.selectedMenu == 2:
            mcnc = mcnc_benchmark_root()
            if self.selectedBenchmarkSubdir:
                source_dirs = [mcnc / self.selectedBenchmarkSubdir]
            else:
                source_dirs = [mcnc]
        elif self.selectedMenu == 3:
            source_dirs = [epfl_benchmark_root()]
        else:
            source_dirs = [
                classic_esop_benchmark_dir(),
                project_root / "classic",
                benchmarks_root(),
            ]

        if file_path.is_absolute():
            if file_path.exists():
                return file_path
            if not file_path.suffix:
                for ext in (".esop", ".pla"):
                    candidate = file_path.with_suffix(ext)
                    if candidate.exists():
                        return candidate
            return file_path

        # if user entered name without extension, search within source directories
        candidates = [file_path] if file_path.suffix else [file_path.with_suffix(ext) for ext in (".esop", ".pla")]
        base_dirs = [
            Path.cwd(),
            Path(__file__).resolve().parent,
            project_root,
        ] + source_dirs

        for candidate in candidates:
            for base in base_dirs:
                resolved = base / candidate
                if resolved.exists():
                    return resolved

        # Search recursively in the selected source directories for name match
        for source_dir in source_dirs:
            if source_dir.exists():
                if file_path.suffix:
                    for resolved in source_dir.rglob(file_path.name):
                        return resolved
                else:
                    for ext in (".esop", ".pla"):
                        pattern = file_path.name + ext
                        for resolved in source_dir.rglob(pattern):
                            return resolved

        return file_path

    def readDataFromESOPFile(self, fileName):
        input_path = self.resolve_input_file(fileName)
        self.esopFileName = str(input_path)
        RPLA.esopFileName = self.esopFileName
        try:
            with open(input_path, "r") as fileObj:
                lines = [line.strip() for line in fileObj if line.strip()]

            esop_output_index = 0
            product_map = {}
            for line in lines:
                if line.startswith("."):
                    self.inputFormat(line)
                elif "^" in line or line == "0":
                    self._parse_esop_output_line(line, esop_output_index, product_map)
                    esop_output_index += 1
                else:
                    self.inputFormat(line)
        except FileNotFoundError:
            print("File Not Found...")

    def _parse_esop_output_line(self, line, output_index, product_map):
        if self.totalOutputs == 0:
            return

        while len(self.functions) < self.totalOutputs:
            self.functions.append(Function(len(self.functions)))

        if output_index >= self.totalOutputs:
            return

        terms = [term.strip() for term in line.split("^")]
        for product in self.products:
            while len(product.functions) <= output_index:
                product.addFunction(-1)

        for term in terms:
            if term == "" or term == "0":
                continue

            pattern = term
            if pattern in product_map:
                product_index = product_map[pattern]
            else:
                product_index = len(self.products)
                new_product = Product(product_index, pattern)
                for _ in range(output_index):
                    new_product.addFunction(-1)
                self.products.append(new_product)
                product_map[pattern] = product_index

            product = self.products[product_index]
            while len(product.functions) < output_index:
                product.addFunction(-1)

            if len(product.functions) == output_index:
                pos = self.functions[output_index].addProduct(product_index)
                product.addFunction(pos)
            elif product.functions[output_index] == -1:
                pos = self.functions[output_index].addProduct(product_index)
                product.functions[output_index] = pos

    def getPatternOfProduct(self, data):
        pattern = ["-"] * self.totalLiterals
        for char in data:
            if char.isupper():
                pattern[ord(char) - 65] = "0"
            elif char.islower():
                pattern[ord(char) - 97] = "1"
        return "".join(pattern)

    def getPatternOfFunction(self, productIndex):
        pattern = ["0"] * self.totalOutputs
        baseProduct = self.patternsOfProduct[productIndex]
        for func_index in baseProduct.functions:
            pattern[func_index] = "1"
        return "".join(pattern)

    def _skip_existing_calculation(self):
        """MCNC/EPFL (web benchmarks) and RPLA_SKIP_EXISTING omit the legacy Existing model."""
        # if os.environ.get("RPLA_SKIP_EXISTING", "").strip().lower() in (
        #     "1",
        #     "true",
        #     "yes",
        #     "on",
        # ):
        return True
        # return self.selectedMenu in (2, 3)

    def inputFormat(self, data):
        tokens = data.split()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.lower() == ".i":
                self.totalLiterals = int(tokens[i + 1])
                i += 2
            elif token.lower() == ".o":
                self.totalOutputs = int(tokens[i + 1])
                i += 2
            elif token.lower() == ".p":
                self.totalProducts = int(tokens[i + 1])
                i += 2
            elif token.lower() == ".e":
                import copy
                from types import SimpleNamespace

                from cost_calculation import CostCalculation
                from existing_calculation import (
                    ExistingCalculation,
                    show_mitra2012_optimized_final,
                )
                from optimized_rpla_calculation import OptimizedRPLACalculation

                snap = SimpleNamespace(
                    functions=copy.deepcopy(self.functions),
                    products=copy.deepcopy(self.products),
                )
                benchmark_two_column = self._skip_existing_calculation()
                costCalculation = CostCalculation(self, quiet=benchmark_two_column)
                costCalculation.xorPlane()
                costCalculation.andPlane()

                opt_calc = OptimizedRPLACalculation(
                    snap, self.totalLiterals, quiet=benchmark_two_column
                )
                opt_calc.xorPlane()
                opt_calc.andPlane()

                if benchmark_two_column:
                    show_mitra2012_optimized_final(self, costCalculation, opt_calc)
                else:
                    existingCalculation = ExistingCalculation(
                        self, costCalculation, quiet=True
                    )
                    existingCalculation.xorPlane()
                    existingCalculation.andPlane()
                    existingCalculation.showFinalResult(opt_calc=opt_calc)
                self.time = 0
                for i in range(self.totalOutputs - 1):
                    for j in range(i + 1, self.totalOutputs):
                        pass
                for i in range(self.totalOutputs):
                    for j in range(self.functions[i].getSize()):
                        pass
                for i in range(self.totalProducts):
                    for j in range(self.products[i].getSize()):
                        pass
                self.time = 0
                for i in range(self.totalProducts - 1):
                    for j in range(i + 1, self.totalProducts):
                        pass
                for i in range(self.totalProducts - 1):
                    for j in range(i + 1, self.totalProducts):
                        pass
                for i in range(self.totalOutputs - 1):
                    for j in range(i + 1, self.totalOutputs):
                        pass
                for i in range(self.totalProducts):
                    for j in range(self.products[i].getSize()):
                        pass
                for i in range(self.totalOutputs):
                    for j in range(self.functions[i].getSize()):
                        pass
                return 0
            else:
                product = Product(len(self.products), token)
                self.products.append(product)
                temp = tokens[i + 1]
                for o in range(self.totalOutputs):
                    if len(self.functions) < o + 1:
                        self.functions.append(Function(o))
                    if temp[o] == '1':
                        pos = self.functions[o].addProduct(len(self.products) - 1)
                        self.products[-1].addFunction(pos)
                    else:
                        self.products[-1].addFunction(-1)
                i += 2
        return 0

    def convertBLIFToESOP(self, fileName, use_exorcism: bool = True):
        """Convert BLIF to ESOP using ABC and optional EXORCISM-4."""
        try:
            # Check if it's a single file or batch directory
            file_path = Path(fileName)
            
            # If it's a directory, do batch conversion
            if file_path.is_dir() or fileName in ("epfl", "mcnc", "both"):
                self._batchConvertBLIFToESOP(fileName, use_exorcism=use_exorcism)
            else:
                # Single file conversion
                self._singleConvertBLIFToESOP(fileName, use_exorcism=use_exorcism)
        except Exception as e:
            print(f"Error converting BLIF to ESOP: {e}")
    
    def _singleConvertBLIFToESOP(self, blif_file, use_exorcism: bool = True):
        """Convert a single BLIF file to ESOP."""
        try:
            pipeline = "ABC + EXORCISM-4" if use_exorcism else "ABC + Custom Parser"
            print(f"\nConverting BLIF to ESOP ({pipeline}): {blif_file}")
            converter = BLIFToESOP(blif_file, use_exorcism=use_exorcism)
            
            if not converter.convert_to_esop():
                print("❌ Conversion failed")
                return
            
            # Generate output filename
            input_path = Path(blif_file)
            output_file = input_path.with_suffix('.esop')
            
            if converter.write_esop_file(str(output_file)):
                print(f"✓ Successfully converted to: {output_file}")
                print(f"  Inputs: {converter.num_inputs}")
                print(f"  Outputs: {converter.num_outputs}")
                print(f"  Products: {len(converter.products)}")
                print(f"  File size: {output_file.stat().st_size} bytes")
            else:
                print("❌ Failed to write ESOP file")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _batchConvertBLIFToESOP(self, source, use_exorcism: bool = True):
        """Batch convert BLIF files from EPFL/MCNC benchmarks (ABC + optional EXORCISM-4)."""
        project_root = Path(__file__).resolve().parent.parent

        # Determine which directories to convert (benchmarks/epfl, benchmarks/mcnc)
        dirs_to_convert = []
        if source == "epfl":
            dirs_to_convert = [epfl_benchmark_root()]
        elif source == "mcnc":
            dirs_to_convert = [mcnc_benchmark_root()]
        elif source == "both":
            dirs_to_convert = [epfl_benchmark_root(), mcnc_benchmark_root()]
        else:
            # Try as a path
            path = Path(source)
            if path.exists() and path.is_dir():
                dirs_to_convert = [path]
            else:
                print(f"Directory not found: {source}")
                return
        
        total_converted = 0
        total_failed = 0
        
        for source_dir in dirs_to_convert:
            if not source_dir.exists():
                print(f"⚠ Directory not found: {source_dir}")
                continue
            
            print(f"\n{'='*70}")
            print(f"Converting BLIF benchmarks in {source_dir.name}")
            print(f"{'='*70}")
            
            converter = BLIFBatchConverter(str(source_dir), use_exorcism=use_exorcism)
            converted, failed = converter.convert_all()
            
            total_converted += converted
            total_failed += failed
        
        print(f"\n{'='*70}")
        print(f"Batch Conversion Complete:")
        print(f"  Total Converted: {total_converted}")
        print(f"  Total Failed:    {total_failed}")
        print(f"{'='*70}")


def main():
    rplaObj = RPLA()
    while True:
        rplaObj.functions = []
        rplaObj.products = []
        rplaObj.patternsOfProduct = []
        rplaObj.totalLiterals = 0
        rplaObj.totalProducts = 0
        rplaObj.totalOutputs = 0
        print("\n" + "="*70)
        print("RPLA - Reversible PLA Synthesis Tool")
        print("="*70)
        print("(1) Calculation of Cost of an ESOP PLA (classic)")
        # print("(2) Calculation of Cost of an ESOP PLA (MCNC)")
        # print("(3) Calculation of Cost of an ESOP PLA (EPFL)")
        # print("(4) Convert SOP Expression into PLA (.pla)")
        # print("(5) Convert ESOP Expression into ESOP PLA (.esop)")
        # print("(6) Convert BLIF to ESOP (ABC + Custom Parser) without EXORCISM-4")
        # print("(7) Batch Convert EPFL/MCNC Benchmarks to ESOP without EXORCISM-4")
        # print("(8) Batch Convert EPFL/MCNC Benchmarks to ESOP (ABC + EXORCISM-4)")
        print("(9) Exit")
        print("="*70)
        # select = input("Please Enter a number between 1 and 9 : ").strip()
        select = input("Please Enter a number 1 or 9 : ").strip()
        if select == "1":
            rplaObj.selectedMenu = 1
            file_name = input("\nEnter File (.esop) Name: ")
            rplaObj.readDataFromESOPFile(file_name)
        elif select == "2":
            rplaObj.selectedMenu = 2
            print("\nMCNC Benchmark Categories:")
            print("  (a) Combinational")
            print("  (b) Sequential")
            category = input("Select category (a/b): ").strip().lower()
            if category == "a":
                rplaObj.selectedBenchmarkSubdir = "Combinational"
            elif category == "b":
                rplaObj.selectedBenchmarkSubdir = "Sequential"
            else:
                print("Invalid selection. Returning to main menu.")
                rplaObj.selectedBenchmarkSubdir = None
                continue
            file_name = input("\nEnter File (.esop) Name: ")
            rplaObj.readDataFromESOPFile(file_name)
        elif select == "3":
            rplaObj.selectedMenu = 3
            rplaObj.selectedBenchmarkSubdir = None
            file_name = input("\nEnter File (.esop) Name: ")
            rplaObj.readDataFromESOPFile(file_name)
        elif select == "4":
            rplaObj.selectedMenu = 2
            file_name = input("\nEnter File Name: ")
            rplaObj.readDataManually(file_name)
        elif select == "5":
            rplaObj.selectedMenu = 3
            file_name = input("\nEnter File Name: ")
            rplaObj.readDataManually(file_name)
        elif select == "6":
            file_name = input("\nEnter BLIF File Path: ")
            rplaObj.convertBLIFToESOP(file_name, use_exorcism=False)
        elif select == "7":
            print("\nBatch conversion (ABC + Custom Parser) without EXORCISM-4")
            print("  (a) EPFL benchmarks")
            print("  (b) MCNC benchmarks")
            print("  (c) Both EPFL and MCNC")
            choice = input("Select option (a/b/c): ").strip().lower()
            if choice == "a":
                rplaObj._batchConvertBLIFToESOP("epfl", use_exorcism=False)
            elif choice == "b":
                rplaObj._batchConvertBLIFToESOP("mcnc", use_exorcism=False)
            elif choice == "c":
                rplaObj._batchConvertBLIFToESOP("both", use_exorcism=False)
            else:
                print("Invalid selection")
        elif select == "8":
            print("\nBatch conversion (ABC + EXORCISM-4)")
            print("  (a) EPFL benchmarks")
            print("  (b) MCNC benchmarks")
            print("  (c) Both EPFL and MCNC")
            choice = input("Select option (a/b/c): ").strip().lower()
            if choice == "a":
                rplaObj._batchConvertBLIFToESOP("epfl", use_exorcism=True)
            elif choice == "b":
                rplaObj._batchConvertBLIFToESOP("mcnc", use_exorcism=True)
            elif choice == "c":
                rplaObj._batchConvertBLIFToESOP("both", use_exorcism=True)
            else:
                print("Invalid selection")
        elif select == "9":
            print("\nThank you for using RPLA. Goodbye!")
            break
        else:
            print("Invalid selection. Please enter a number between 1 and 9.")


if __name__ == "__main__":
    main()
