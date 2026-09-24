#pragma once
#include "ui/record_store.hpp"
namespace lezac::diagnostics {
class UiDiagnostics {
public:
    static void debugRecordUpdate(const ui::RecordStore& store, const std::string& path);
    static void debugRecordsRawRoundtrip(const ui::RecordStore& store);
    static void debugRecordEntryStaticModel();
    static void debugEndFlowStaticModel();
};
}
