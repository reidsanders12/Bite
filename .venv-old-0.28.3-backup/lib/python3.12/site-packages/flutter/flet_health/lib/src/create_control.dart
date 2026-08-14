import 'package:flet/flet.dart';
import 'flet_health.dart';

CreateControlFactory createControl = (CreateControlArgs args) {
  switch (args.control.type) {
    case "flet_health":
      if (args.parent == null) {
        throw ArgumentError('Parent cannot be null');
      }
      return FletHealthControl(
        parent: args.parent!,
          control: args.control,
          backend: args.backend
      );
    default:
      return null;
  }
};

void ensureInitialized() {
  // Required initializations, if any
  // Se houver inicializações necessárias
}
